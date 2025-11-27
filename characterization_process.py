import json
import os
import sys
import subprocess
import csv
from datetime import datetime
from scipy.optimize import minimize
import shutil

def load_json(json_path):
    with open(json_path, 'r', encoding='utf-8-sig') as f: # Use utf-8-sig to handle BOM if present
        content = f.read()
        # print(f"DEBUG: Reading {json_path}, length: {len(content)}")
        # print(f"DEBUG: First 100 chars: {content[:100]}")
        return json.loads(content)

def save_json(data, json_path):
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

def get_signal_layers(stackup_data):
    signal_layers = []
    for i, layer in enumerate(stackup_data['rows']):
        if layer['type'] == 'conductor' and layer.get('width') and layer.get('spacing'):
            signal_layers.append(i)
    return signal_layers

def extract_layer_params(stackup_data, layer_index):
    # Extract parameters relevant for optimization for a specific signal layer
    # We need to look at the signal layer itself, and the dielectrics above and below
    
    rows = stackup_data['rows']
    layer = rows[layer_index]
    
    # Find immediate dielectric layers
    # Note: This simple logic assumes alternating conductor/dielectric or similar structure
    # A more robust approach would be to traverse up/down until a conductor is found or end of stack
    
    # For this specific JSON structure, let's look at immediate neighbors
    # If immediate neighbor is not dielectric, we might need to look further?
    # Based on the file provided, it seems consistent.
    
    # Let's just grab the immediate neighbors for now as per the plan description
    # "dielectric layers immediately above and below (physical ordering)"
    
    diel_above_idx = layer_index - 1
    diel_below_idx = layer_index + 1
    
    # Check bounds
    diel_above = rows[diel_above_idx] if diel_above_idx >= 0 and rows[diel_above_idx]['type'] == 'dielectric' else None
    diel_below = rows[diel_below_idx] if diel_below_idx < len(rows) and rows[diel_below_idx]['type'] == 'dielectric' else None
    
    return {
        'layer_index': layer_index,
        'diel_above_index': diel_above_idx if diel_above else None,
        'diel_below_index': diel_below_idx if diel_below else None,
        'layer': layer,
        'diel_above': diel_above,
        'diel_below': diel_below
    }

def create_modeling_params(stackup_data, layer_params, current_values, output_aedb_path):
    # Construct the params dictionary expected by modeling.py
    # current_values is a dict of optimized parameters
    
    layer = layer_params['layer']
    diel_above = layer_params['diel_above']
    diel_below = layer_params['diel_below']
    
    # Update local copies with current optimized values
    # We need to map the flat optimization vector back to these structures
    
    # Construct the layers list for modeling.py
    # We only need the signal layer and its reference planes/dielectrics?
    # modeling.py expects a list of layers. 
    # Based on modeling.py example, it builds a mini-stackup: Top (Signal), Diel, Gnd.
    # But the real stackup might be more complex (Stripline: Gnd, Diel, Signal, Diel, Gnd).
    
    # Let's look at reference_layers string: "gnd1 / gnd2"
    ref_layers_str = layer.get('reference_layers', '')
    refs = [r.strip() for r in ref_layers_str.split('/')]
    
    # We need to find the actual layer objects for these references to get their properties if needed
    # But modeling.py just draws rectangles for them.
    
    # Construct a subset of layers for the simulation model
    # For a stripline (most complex): RefTop, DielTop, Signal, DielBot, RefBot
    
    model_layers = []
    
    # Helper to create layer dict
    def make_layer_dict(l_data, override_params=None):
        d = {
            "layername": l_data['layername'],
            "type": "signal" if l_data['type'] == 'conductor' else "dielectric",
            "thickness": f"{l_data['thickness']}mil", # Assuming input is mil? JSON doesn't specify unit, but modeling.py uses mil. 
            # WAIT: JSON values like "1.9", "3.47". modeling.py uses "1.2mil".
            # We should probably assume the JSON values are in mil if not specified.
        }
        
        if override_params:
            for k, v in override_params.items():
                d[k] = v # override
                if k == 'thickness':
                     d[k] = f"{v}mil"

        if d['type'] == 'signal':
            d['material'] = "copper" # Default
            d['etch_factor'] = float(l_data.get('etchfactor', 0))
            d['hallhuray_surface_ratio'] = float(l_data.get('hallhuray_surface_ratio', 0))
            d['nodule_radius'] = f"{l_data.get('nodule_radius', 0)}um"
            
            # Override
            if override_params:
                if 'etch_factor' in override_params: d['etch_factor'] = override_params['etch_factor']
                if 'hallhuray_surface_ratio' in override_params: d['hallhuray_surface_ratio'] = override_params['hallhuray_surface_ratio']
                if 'nodule_radius' in override_params: d['nodule_radius'] = f"{override_params['nodule_radius']}um"

        else:
            d['dk'] = float(l_data.get('dk', 1))
            d['df'] = float(l_data.get('df', 0))
            
            # Override
            if override_params:
                if 'dk' in override_params: d['dk'] = override_params['dk']
                if 'df' in override_params: d['df'] = override_params['df']
        
        return d

    # We need to construct the stackup from top to bottom
    # If stripline: RefTop -> DielTop -> Signal -> DielBot -> RefBot
    
    # Top Reference
    ref_top_name = refs[0] if len(refs) > 0 and refs[0] != 'None' else None
    ref_bot_name = refs[1] if len(refs) > 1 and refs[1] != 'None' else None
    
    # We need to find the layers in the original stackup to build the model stackup correctly
    # This is a bit tricky because we need to know the order.
    # The original JSON `rows` is ordered top to bottom.
    
    # Let's just include the layers involved:
    # 1. Top Ref (if any)
    # 2. Diel Above (if any)
    # 3. Signal
    # 4. Diel Below (if any)
    # 5. Bot Ref (if any)
    
    # We need to extract these from the full `rows` list
    
    # ... Implementation detail: finding ref layers by name ...
    def find_layer_by_name(name):
        for l in stackup_data['rows']:
            if l['layername'] == name:
                return l
        return None

    if ref_top_name:
        l = find_layer_by_name(ref_top_name)
        if l: model_layers.append(make_layer_dict(l))
        
    if diel_above:
        # Check if we have overrides for this dielectric
        overrides = {}
        if 'dk_up' in current_values: overrides['dk'] = current_values['dk_up']
        if 'df_up' in current_values: overrides['df'] = current_values['df_up']
        model_layers.append(make_layer_dict(diel_above, overrides))
        
    # Signal Layer
    sig_overrides = {}
    if 'thickness' in current_values: sig_overrides['thickness'] = current_values['thickness']
    if 'etch_factor' in current_values: sig_overrides['etch_factor'] = current_values['etch_factor']
    if 'hallhuray_surface_ratio' in current_values: sig_overrides['hallhuray_surface_ratio'] = current_values['hallhuray_surface_ratio']
    if 'nodule_radius' in current_values: sig_overrides['nodule_radius'] = current_values['nodule_radius']
    
    model_layers.append(make_layer_dict(layer, sig_overrides))
    
    if diel_below:
        overrides = {}
        if 'dk_down' in current_values: overrides['dk'] = current_values['dk_down']
        if 'df_down' in current_values: overrides['df'] = current_values['df_down']
        model_layers.append(make_layer_dict(diel_below, overrides))
        
    if ref_bot_name:
        l = find_layer_by_name(ref_bot_name)
        if l: model_layers.append(make_layer_dict(l))

    # Trace params
    trace_params = {
        "width_mil": float(layer['width']),
        "spacing_mil": float(layer['spacing'])
    }
    
    # Ref layers list for port creation/rectangles
    ref_layers_list = []
    if ref_top_name: ref_layers_list.append(ref_top_name)
    if ref_bot_name: ref_layers_list.append(ref_bot_name)

    return {
        "output_aedb_path": output_aedb_path,
        "frequency": stackup_data['frequency'],
        "target_layer": layer['layername'],
        "trace_params": trace_params,
        "ref_layers": ref_layers_list,
        "layers": model_layers
    }

def run_optimization(stackup_data, signal_layer_index, output_dir, log_file):
    layer_info = extract_layer_params(stackup_data, signal_layer_index)
    layer = layer_info['layer']
    
    print(f"Characterizing layer: {layer['layername']}")
    
    # Target values
    target_z = float(layer['impedance_target'])
    target_loss = float(layer['loss_target']) # This might be negative in JSON? "loss_target": "-0.86"
    # We should probably treat loss as absolute value for error calculation or match sign?
    # Usually loss is negative dB.
    
    # Initial values
    initial_values = {
        'thickness': float(layer['thickness']),
        'etch_factor': float(layer['etchfactor']),
        'hallhuray_surface_ratio': float(layer['hallhuray_surface_ratio']),
        'nodule_radius': float(layer['nodule_radius']),
    }
    
    if layer_info['diel_above']:
        initial_values['dk_up'] = float(layer_info['diel_above']['dk'])
        initial_values['df_up'] = float(layer_info['diel_above']['df'])
        
    if layer_info['diel_below']:
        initial_values['dk_down'] = float(layer_info['diel_below']['dk'])
        initial_values['df_down'] = float(layer_info['diel_below']['df'])
        
    # Optimization vector (list of values)
    # Order: etch_factor, thickness, dk_up, dk_down, df_up, df_down, surface_ratio, nodule_radius
    # We need to map back and forth
    
    keys = list(initial_values.keys())
    x0 = [initial_values[k] for k in keys]
    
    # Bounds (from settings)
    settings = stackup_data['settings']
    bounds = []
    for k in keys:
        val = initial_values[k]
        variation = 0.2 # Default 20%
        if 'etch_factor' in k: variation = float(settings['etchfactor']['variation'].strip('%'))/100
        elif 'thickness' in k: variation = float(settings['thickness']['variation'].strip('%'))/100
        elif 'dk' in k: variation = float(settings['dk']['variation'].strip('%'))/100
        elif 'df' in k: variation = float(settings['df']['variation'].strip('%'))/100
        elif 'surface_ratio' in k: variation = float(settings['hallhuray_surface_ratio']['variation'].strip('%'))/100
        elif 'nodule_radius' in k: variation = float(settings['nodule_radius']['variation'].strip('%'))/100
        
        # Etch factor is negative, so bounds logic needs care
        # If val is -2.5, +/- 20% -> -3.0 to -2.0
        # If val is positive, normal logic
        
        lower = val * (1 - variation) if val > 0 else val * (1 + variation)
        upper = val * (1 + variation) if val > 0 else val * (1 - variation)
        
        # Ensure lower < upper
        if lower > upper: lower, upper = upper, lower
        
        bounds.append((lower, upper))

    iteration_count = 0

    def objective(x):
        nonlocal iteration_count
        iteration_count += 1
        
        # Map x back to dict
        current_vals = dict(zip(keys, x))
        
        # Create temp params file
        temp_params_path = os.path.join(output_dir, f"params_{layer['layername']}_{iteration_count}.json")
        aedb_path = os.path.join(output_dir, f"sim_{layer['layername']}_{iteration_count}.aedb")
        
        modeling_params = create_modeling_params(stackup_data, layer_info, current_vals, aedb_path)
        save_json(modeling_params, temp_params_path)
        
        # Run Modeling
        print(f"  Iter {iteration_count}: Running Modeling...")
        subprocess.run([sys.executable, "modeling.py", temp_params_path], check=True)
        
        # Run Simulation
        print(f"  Iter {iteration_count}: Running Simulation...")
        result = subprocess.run([sys.executable, "simulation.py", aedb_path], capture_output=True, text=True, check=True)
        
        # Parse Output
        # Expected: "RESULT: <zdiff>, <dbs21>"
        zdiff = 0
        dbs21 = 0
        for line in result.stdout.splitlines():
            if line.startswith("RESULT:"):
                parts = line.split(":")[1].split(",")
                zdiff = float(parts[0])
                dbs21 = float(parts[1])
                break
        
        print(f"  Iter {iteration_count}: Result Zdiff={zdiff:.2f}, S21={dbs21:.2f}")
        
        # Calculate Error
        # Zdiff error
        z_error = abs(zdiff - target_z) / target_z
        
        # Loss error
        # If target is -0.86, and we get -0.9, error is abs(-0.9 - (-0.86)) / abs(-0.86)
        loss_error = abs(dbs21 - target_loss) / abs(target_loss)
        
        total_error = z_error + loss_error
        
        # Log
        with open(log_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # | iteration | layer | width | spacing | thickness | etch_factor | dk_up | dk_down | df_up | df_down | Zdiff | S21 | pass? |
            
            row = [
                iteration_count,
                layer['layername'],
                layer['width'],
                layer['spacing'],
                current_vals.get('thickness', ''),
                current_vals.get('etch_factor', ''),
                current_vals.get('dk_up', ''),
                current_vals.get('dk_down', ''),
                current_vals.get('df_up', ''),
                current_vals.get('df_down', ''),
                zdiff,
                dbs21,
                total_error < 0.02 # Rough pass check
            ]
            writer.writerow(row)
            
        return total_error

    # Run optimization
    # Use 'SLSQP' or 'Nelder-Mead'
    # Since we have bounds, SLSQP or L-BFGS-B is good.
    # However, these simulations are expensive. We probably want very few iterations.
    # The user mentioned "iterative optimization" but didn't specify algorithm.
    # Let's try Nelder-Mead with loose tolerance to avoid too many calls, or just a few steps.
    # Or 'SLSQP' with bounds.
    
    print("Starting optimization...")
    res = minimize(objective, x0, bounds=bounds, method='Nelder-Mead', tol=0.01, options={'maxiter': 10})
    
    print(f"Optimization finished. Success: {res.success}")
    return dict(zip(keys, res.x))

def main():
    input_json = "stackup_layers_1007.json"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"stackup_characterization_{ts}"
    os.makedirs(output_dir, exist_ok=True)
    
    log_file = os.path.join(output_dir, "characterization_log.csv")
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "layer", "width", "spacing", "thickness", "etch_factor", "dk_up", "dk_down", "df_up", "df_down", "Zdiff", "S21", "pass?"])

    data = load_json(input_json)
    signal_indices = get_signal_layers(data)
    
    print(f"Found {len(signal_indices)} signal layers to characterize.")
    
    for idx in signal_indices:
        optimized_params = run_optimization(data, idx, output_dir, log_file)
        
        # Update data with optimized params
        layer = data['rows'][idx]
        if 'thickness' in optimized_params: layer['thickness'] = str(optimized_params['thickness'])
        if 'etch_factor' in optimized_params: layer['etchfactor'] = str(optimized_params['etch_factor'])
        if 'hallhuray_surface_ratio' in optimized_params: layer['hallhuray_surface_ratio'] = str(optimized_params['hallhuray_surface_ratio'])
        if 'nodule_radius' in optimized_params: layer['nodule_radius'] = str(optimized_params['nodule_radius'])
        
        # Update dielectrics
        layer_info = extract_layer_params(data, idx)
        if layer_info['diel_above']:
            if 'dk_up' in optimized_params: layer_info['diel_above']['dk'] = str(optimized_params['dk_up'])
            if 'df_up' in optimized_params: layer_info['diel_above']['df'] = str(optimized_params['df_up'])
            
        if layer_info['diel_below']:
            if 'dk_down' in optimized_params: layer_info['diel_below']['dk'] = str(optimized_params['dk_down'])
            if 'df_down' in optimized_params: layer_info['diel_below']['df'] = str(optimized_params['df_down'])

    final_json_path = os.path.join(output_dir, "characterized_stackup.json")
    save_json(data, final_json_path)
    print(f"Characterization complete. Saved to {final_json_path}")

if __name__ == "__main__":
    main()
