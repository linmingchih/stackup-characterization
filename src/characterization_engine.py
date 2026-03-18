import json
import os
import sys
import subprocess
import csv
import time
from datetime import datetime
from scipy.optimize import minimize
import shutil

# Helper functions from original script
def format_float(val):
    return "{:.9f}".format(float(val)).rstrip('0').rstrip('.')

def get_signal_layers(stackup_data):
    signal_layers = []
    for i, layer in enumerate(stackup_data['rows']):
        if layer['type'] == 'conductor' and layer.get('width') and layer.get('spacing'):
            signal_layers.append(i)
    return signal_layers

def extract_layer_params(stackup_data, layer_index):
    rows = stackup_data['rows']
    layer = rows[layer_index]
    
    # Search upwards for the nearest dielectric
    diel_above = None
    diel_above_idx = None
    for j in range(layer_index - 1, -1, -1):
        if rows[j]['type'] == 'dielectric':
            diel_above = rows[j]
            diel_above_idx = j
            break
            
    # Search downwards for the nearest dielectric
    diel_below = None
    diel_below_idx = None
    for j in range(layer_index + 1, len(rows)):
        if rows[j]['type'] == 'dielectric':
            diel_below = rows[j]
            diel_below_idx = j
            break
    
    return {
        'layer_index': layer_index,
        'diel_above_index': diel_above_idx,
        'diel_below_index': diel_below_idx,
        'layer': layer,
        'diel_above': diel_above,
        'diel_below': diel_below
    }

def create_modeling_params(stackup_data, layer_params, current_values, output_aedb_path, signal_half, max_delta_s=0.02, freq_stop=5):
    layer = layer_params['layer']
    diel_above = layer_params['diel_above']
    diel_below = layer_params['diel_below']
    
    ref_layers_str = layer.get('reference_layers', '')
    refs = [r.strip() for r in ref_layers_str.split('/')]
    
    model_layers = []
    
    def make_layer_dict(l_data, override_params=None):
        d = {
            "layername": l_data['layername'],
            "type": "signal" if l_data['type'] == 'conductor' else "dielectric",
            "thickness": f"{l_data['thickness']}mil",
        }
        
        if override_params:
            for k, v in override_params.items():
                d[k] = v
                if k == 'thickness':
                     d[k] = f"{v}mil"

        if d['type'] == 'signal':
            d['material'] = "copper"
            d['etch_factor'] = float(l_data.get('etchfactor', 0))
            d['hallhuray_surface_ratio'] = float(l_data.get('hallhuray_surface_ratio', 0))
            d['nodule_radius'] = f"{l_data.get('nodule_radius', 0)}um"
            
            if override_params:
                if 'etch_factor' in override_params: d['etch_factor'] = override_params['etch_factor']
                if 'hallhuray_surface_ratio' in override_params: d['hallhuray_surface_ratio'] = override_params['hallhuray_surface_ratio']
                if 'nodule_radius' in override_params: d['nodule_radius'] = f"{override_params['nodule_radius']}um"

        else:
            dk_val = float(l_data.get('dk', 1))
            df_val = float(l_data.get('df', 0))
            
            if override_params:
                if 'dk' in override_params: dk_val = override_params['dk']
                if 'df' in override_params: df_val = override_params['df']
            
            d['dk'] = format_float(dk_val)
            d['df'] = format_float(df_val)
            d['material_name'] = f"mat_{l_data['layername']}"
        
        return d

    def find_layer_by_name(name):
        for l in stackup_data['rows']:
            if l['layername'] == name:
                return l
        return None

    ref_top_name = refs[0] if len(refs) > 0 and refs[0] != 'None' else None
    ref_bot_name = refs[1] if len(refs) > 1 and refs[1] != 'None' else None

    if ref_top_name:
        l = find_layer_by_name(ref_top_name)
        if l: model_layers.append(make_layer_dict(l))
        
    if diel_above:
        overrides = {}
        if 'dk_up' in current_values: overrides['dk'] = current_values['dk_up']
        if 'df_up' in current_values: overrides['df'] = current_values['df_up']
        model_layers.append(make_layer_dict(diel_above, overrides))
        
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

    trace_params = {
        "width_mil": float(layer['width']),
        "spacing_mil": float(layer['spacing'])
    }
    
    ref_layers_list = []
    if ref_top_name: ref_layers_list.append(ref_top_name)
    if ref_bot_name: ref_layers_list.append(ref_bot_name)

    return {
        "output_aedb_path": output_aedb_path,
        "frequency": stackup_data['frequency'],
        "max_delta_s": max_delta_s,
        "freq_stop": freq_stop,
        "target_layer": layer['layername'],
        "trace_params": trace_params,
        "ref_layers": ref_layers_list,
        "layers": model_layers,
        "signal_half": signal_half,
        "copper_conductivity": stackup_data.get('copper_conductivity', 5.8e7)
    }

def save_json(data, json_path):
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

class CharacterizationEngine:
    def __init__(self, json_data, max_iter, log_callback=None, stats_callback=None, output_base_dir=None, symmetry=False, max_delta_s=0.02, freq_stop=5):
        self.data = json_data
        self.max_iter = max_iter
        self.log_callback = log_callback
        self.stats_callback = stats_callback
        self.symmetry = symmetry
        self.max_delta_s = max_delta_s
        self.freq_stop = freq_stop
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = output_base_dir if output_base_dir else os.getcwd()
        self.output_dir = os.path.join(base, f"stackup_characterization_{ts}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.log_file = os.path.join(self.output_dir, "characterization_log.csv")
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["iteration", "layer", "width", "spacing", "thickness", "etch_factor", "hallhuray_surface_ratio", "nodule_radius", "dk_up", "dk_down", "df_up", "df_down", "Zdiff", "S21", "pass?"])

    def log(self, msg):
        print(msg)
        if self.log_callback:
            self.log_callback(msg)

    def update_stats(self, layer_name, stats):
        if self.stats_callback:
            self.stats_callback(layer_name, stats)

    def run(self):
        self.log(f"Starting characterization. Output dir: {self.output_dir}")
        self.log(f"Symmetry Mode: {'Enabled' if self.symmetry else 'Disabled'}")
        
        signal_indices = get_signal_layers(self.data)
        self.log(f"Found {len(signal_indices)} signal layers to characterize.")
        
        midpoint = len(signal_indices) // 2
        
        for i, idx in enumerate(signal_indices):
            layer_name = self.data['rows'][idx]['layername']
            
            if self.symmetry and i >= midpoint:
                self.log(f"Skipping optimization for bottom layer {layer_name} (Symmetry enabled)")
                continue

            signal_half = "top" if i < midpoint else "bottom"
            optimized_params = self.optimize_layer(idx, signal_half)
            
            # Update data with optimized params
            layer = self.data['rows'][idx]
            if 'thickness' in optimized_params: layer['thickness'] = str(optimized_params['thickness'])
            if 'etch_factor' in optimized_params: layer['etchfactor'] = str(optimized_params['etch_factor'])
            if 'hallhuray_surface_ratio' in optimized_params: layer['hallhuray_surface_ratio'] = str(optimized_params['hallhuray_surface_ratio'])
            if 'nodule_radius' in optimized_params: layer['nodule_radius'] = str(optimized_params['nodule_radius'])
            
            layer_info = extract_layer_params(self.data, idx)
            if layer_info['diel_above']:
                if 'dk_up' in optimized_params: layer_info['diel_above']['dk'] = str(optimized_params['dk_up'])
                if 'df_up' in optimized_params: layer_info['diel_above']['df'] = str(optimized_params['df_up'])
                
            if layer_info['diel_below']:
                if 'dk_down' in optimized_params: layer_info['diel_below']['dk'] = str(optimized_params['dk_down'])
                if 'df_down' in optimized_params: layer_info['diel_below']['df'] = str(optimized_params['df_down'])

            # Apply to symmetric layer if enabled
            if self.symmetry:
                sym_idx_in_list = len(signal_indices) - 1 - i
                if sym_idx_in_list > i: # Ensure we don't double apply to middle layer if odd count
                    sym_layer_idx = signal_indices[sym_idx_in_list]
                    sym_layer_name = self.data['rows'][sym_layer_idx]['layername']
                    self.log(f"Applying symmetric params from {layer_name} to {sym_layer_name}")
                    
                    sym_layer = self.data['rows'][sym_layer_idx]
                    if 'thickness' in optimized_params: sym_layer['thickness'] = str(optimized_params['thickness'])
                    if 'etch_factor' in optimized_params: sym_layer['etchfactor'] = str(optimized_params['etch_factor'])
                    if 'hallhuray_surface_ratio' in optimized_params: sym_layer['hallhuray_surface_ratio'] = str(optimized_params['hallhuray_surface_ratio'])
                    if 'nodule_radius' in optimized_params: sym_layer['nodule_radius'] = str(optimized_params['nodule_radius'])
                    
                    sym_layer_info = extract_layer_params(self.data, sym_layer_idx)
                    
                    # Map Top-Up -> Bottom-Down, Top-Down -> Bottom-Up
                    # diel_above (Top) -> diel_below (Bottom)
                    if sym_layer_info['diel_below']:
                         if 'dk_up' in optimized_params: sym_layer_info['diel_below']['dk'] = str(optimized_params['dk_up'])
                         if 'df_up' in optimized_params: sym_layer_info['diel_below']['df'] = str(optimized_params['df_up'])
                    
                    # diel_below (Top) -> diel_above (Bottom)
                    if sym_layer_info['diel_above']:
                         if 'dk_down' in optimized_params: sym_layer_info['diel_above']['dk'] = str(optimized_params['dk_down'])
                         if 'df_down' in optimized_params: sym_layer_info['diel_above']['df'] = str(optimized_params['df_down'])
                    
                    # Update stats for symmetric layer to show it's done
                    self.update_stats(sym_layer_name, {
                        "status": "Done (Sym)",
                        "iterations": "-",
                        "target_z": float(sym_layer.get('impedance_target', 0)),
                        "target_loss": float(sym_layer.get('loss_target', 0)),
                        "best_z": "-",
                        "best_loss": "-",
                        "time_elapsed": "-"
                    })

        # Final Step: Create Full Stackup
        self.log("Creating full stackup model...")
        final_json_path = os.path.join(self.output_dir, "characterized_stackup.json")
        save_json(self.data, final_json_path)
        
        full_aedb_path = os.path.join(self.output_dir, "full_stackup.aedb")
        
        # Call modeling.py to create full stackup
        # We need to implement create_full_stackup in modeling.py and call it here
        # Or we can just call it via subprocess if we add a flag to modeling.py
        # But better to import it if possible, or create a separate script.
        # Since modeling.py is a script, let's just use subprocess with a special flag or new script?
        # The plan said "Modify modeling.py".
        # Let's assume we can call it via subprocess by passing a special "mode" in the json or a different argument.
        # Or just create a temporary json for full stackup and run modeling.py with a flag.
        
        # Actually, let's just add a new CLI entry point to modeling.py or a new function we can call via a wrapper script.
        # Since we are in python, we can't easily import modeling.py if it has top-level code that runs.
        # But modeling.py has `if __name__ == "__main__":`.
        # So we could import it if we fix the path.
        # But `gui_app.py` imports `CharacterizationEngine`.
        # `CharacterizationEngine` is here.
        # `modeling.py` uses `pyedb` which might conflict with `pywebview` if run in same process? 
        # Usually AEDT scripting is safer in subprocess.
        
        # Let's create a temp json for full stackup creation
        full_stackup_params = {
            "mode": "full_stackup",
            "output_aedb_path": full_aedb_path,
            "stackup_data": self.data,
            "copper_conductivity": self.data.get('copper_conductivity', 5.8e7)
        }
        temp_full_path = os.path.join(self.output_dir, "full_stackup_params.json")
        save_json(full_stackup_params, temp_full_path)
        
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            modeling_script = os.path.join(script_dir, "modeling.py")
            subprocess.run([sys.executable, modeling_script, temp_full_path], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.log(f"Full stackup created at {full_aedb_path}")
        except Exception as e:
            self.log(f"Failed to create full stackup: {e}")

        self.log(f"Characterization complete. Saved to {final_json_path}")

    def optimize_layer(self, layer_index, signal_half):
        layer_info = extract_layer_params(self.data, layer_index)
        layer = layer_info['layer']
        layer_name = layer['layername']
        
        self.log(f"Characterizing layer: {layer_name}")
        
        target_z = float(layer['impedance_target'])
        target_loss = float(layer['loss_target'])
        
        # Initial stats
        stats = {
            "status": "Running",
            "iterations": 0,
            "target_z": target_z,
            "target_loss": target_loss,
            "best_z": 0,
            "best_loss": 0,
            "time_elapsed": "0s"
        }
        self.update_stats(layer_name, stats)
        start_time = time.time()

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
            
        keys = list(initial_values.keys())
        x0 = [initial_values[k] for k in keys]
        
        # Bounds
        settings = self.data['settings']
        bounds = []
        for k in keys:
            val = initial_values[k]
            variation = 0.2
            if 'etch_factor' in k: variation = float(settings['etchfactor']['variation'].strip('%'))/100
            elif 'thickness' in k: variation = float(settings['thickness']['variation'].strip('%'))/100
            elif 'dk' in k: variation = float(settings['dk']['variation'].strip('%'))/100
            elif 'df' in k: variation = float(settings['df']['variation'].strip('%'))/100
            elif 'surface_ratio' in k: variation = float(settings['hallhuray_surface_ratio']['variation'].strip('%'))/100
            elif 'nodule_radius' in k: variation = float(settings['nodule_radius']['variation'].strip('%'))/100
            
            lower = val * (1 - variation) if val > 0 else val * (1 + variation)
            upper = val * (1 + variation) if val > 0 else val * (1 - variation)
            if lower > upper: lower, upper = upper, lower
            bounds.append((lower, upper))
            
        # Capture initial signs for Etch Factor constraint
        initial_etch_sign = 1.0
        if 'etch_factor' in initial_values:
            initial_etch_sign = 1.0 if initial_values['etch_factor'] >= 0 else -1.0

        # Tolerances
        z_tol_percent = float(settings['impedance_target']['tolerance'].strip('%')) / 100
        loss_tol_percent = float(settings['loss_target']['tolerance'].strip('%')) / 100

        # Tracking best
        best_error = float('inf')
        best_x = x0
        best_metrics = (0, 0) # z, loss
        current_metrics = (0, 0)
        
        iteration_count = 0
        evaluated_history = []  # To cache objective evaluations and avoid duplicates


        def objective(x):
            nonlocal iteration_count, best_error, best_x, best_metrics, current_metrics, evaluated_history
            
            # Check max iter
            if iteration_count >= self.max_iter:
                return best_error + 1000 

            # Check cache to avoid duplicate simulations
            for past_x, past_metrics, past_error in evaluated_history:
                # If parameters are virtually identical
                if all(abs(a - b) < 1e-6 for a, b in zip(x, past_x)):
                    current_metrics = past_metrics
                    return past_error

            iteration_count += 1
            current_vals = dict(zip(keys, x))
            
            # Temp files
            temp_params_path = os.path.join(self.output_dir, f"params_{layer_name}_{iteration_count}.json")
            aedb_path = os.path.join(self.output_dir, f"sim_{layer_name}_{iteration_count}.aedb")
            
            modeling_params = create_modeling_params(self.data, layer_info, current_vals, aedb_path, signal_half,
                                                   max_delta_s=self.max_delta_s, freq_stop=self.freq_stop)
            save_json(modeling_params, temp_params_path)
            
            # Run Modeling
            self.log(f"[{layer_name}] Iter {iteration_count}: Modeling...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            modeling_script = os.path.join(script_dir, "modeling.py")
            subprocess.run([sys.executable, modeling_script, temp_params_path], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Run Simulation
            self.log(f"[{layer_name}] Iter {iteration_count}: Simulating...")
            simulation_script = os.path.join(script_dir, "simulation.py")
            result = subprocess.run([sys.executable, simulation_script, aedb_path], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            zdiff = 0
            dbs21 = 0
            for line in result.stdout.splitlines():
                if line.startswith("RESULT:"):
                    parts = line.split(":")[1].split(",")
                    zdiff = float(parts[0])
                    dbs21 = float(parts[1])
                    break
            
            self.log(f"[{layer_name}] Iter {iteration_count}: Zdiff={zdiff:.2f}, S21={dbs21:.2f}")
            
            current_metrics = (zdiff, dbs21)

            z_error = abs(zdiff - target_z) / target_z
            loss_error = abs(dbs21 - target_loss) / abs(target_loss)
            # Prioritize Target Z over Target Loss
            total_error = 5.0 * z_error + loss_error
            
            # Update Best
            if total_error < best_error:
                best_error = total_error
                best_x = x
                best_metrics = (zdiff, dbs21)
            
            # Log to CSV
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                row = [
                    iteration_count, layer_name, layer['width'], layer['spacing'],
                    current_vals.get('thickness', ''), current_vals.get('etch_factor', ''),
                    current_vals.get('hallhuray_surface_ratio', ''), current_vals.get('nodule_radius', ''),
                    current_vals.get('dk_up', ''), current_vals.get('dk_down', ''),
                    current_vals.get('df_up', ''), current_vals.get('df_down', ''),
                    zdiff, dbs21, total_error < 0.02
                ]
                writer.writerow(row)
            
            # Update Stats
            stats['iterations'] = iteration_count
            stats['best_z'] = best_metrics[0]
            stats['best_loss'] = best_metrics[1]
            stats['time_elapsed'] = f"{int(time.time() - start_time)}s"
            self.update_stats(layer_name, stats)
            
            evaluated_history.append((list(x), current_metrics, total_error))
            return total_error

        # Custom optimization loop using binary search based on prompt rules
        current_x = list(x0)
        
        # Group parameters
        z_params = [
            ('etch_factor', 'etch_factor'),
            ('dk', ['dk_up', 'dk_down']),
            ('thickness', 'thickness')
        ]
        
        loss_params = [
            ('df', ['df_up', 'df_down']),
            ('hallhuray_surface_ratio', 'hallhuray_surface_ratio'),
            ('nodule_radius', 'nodule_radius')
        ]

        def get_indices(param_map):
            if isinstance(param_map, list): return [keys.index(k) for k in param_map if k in keys]
            elif param_map in keys: return [keys.index(param_map)]
            return []

        def get_param_z_dir(param_name, current_val):
            # Returns 1 if Param UP -> Z UP, -1 if Param UP -> Z DOWN
            if param_name == 'etch_factor': return 1 if current_val < 0 else -1
            if param_name == 'dk': return -1
            if param_name == 'thickness': return 1
            return 1
            
        def get_param_s21_dir(param_name):
            # All loss params UP -> Loss UP -> S21 DOWN (more negative S21). Return -1.
            return -1

        # Intial Sim
        _ = objective(current_x)
        
        try:
            # Phase 1: Impedance Optimization
            z_err = abs((target_z - current_metrics[0]) / target_z)
            if z_err > z_tol_percent:
                self.log(f"[{layer_name}] Phase 1: Impedance Optimization")
                for p_name, p_keys in z_params:
                    if iteration_count >= self.max_iter: break
                    p_indices = get_indices(p_keys)
                    if not p_indices: continue
                    p_idx = p_indices[0]
                    bound_min, bound_max = bounds[p_idx]
                    if bound_min == bound_max: continue # Variation = 0%
                        
                    z_err = abs((target_z - current_metrics[0]) / target_z)
                    if z_err <= z_tol_percent: break
                    
                    need_z_up = target_z > current_metrics[0]
                    p_dir = get_param_z_dir(p_name, current_x[p_idx])
                    need_param_up = (need_z_up and p_dir > 0) or (not need_z_up and p_dir < 0)
                    
                    L_val = current_x[p_idx]
                    R_val = bound_max if need_param_up else bound_min
                    
                    # 1. Test Boundary (First step for this parameter)
                    test_x = list(current_x)
                    for i in p_indices: test_x[i] = R_val
                    _ = objective(test_x)
                    
                    z_err = abs((target_z - current_metrics[0]) / target_z)
                    if z_err <= z_tol_percent:
                        current_x = test_x
                        break
                        
                    new_need_z_up = target_z > current_metrics[0]
                    new_p_dir = get_param_z_dir(p_name, test_x[p_idx])
                    new_need_param_up = (new_need_z_up and new_p_dir > 0) or (not new_need_z_up and new_p_dir < 0)
                    
                    if new_need_param_up == need_param_up:
                        self.log(f"[{layer_name}] {p_name} hit boundary, moving to next.")
                        current_x = test_x # Keep at boundary and move on
                        continue
                        
                    # 2. Binary Search
                    self.log(f"[{layer_name}] {p_name} overshot, starting binary search.")
                    val_need_up = L_val if need_param_up else R_val
                    val_need_down = R_val if need_param_up else L_val
                    
                    for _ in range(10): # Max 10 bs steps per param
                        if iteration_count >= self.max_iter: break
                        mid = (val_need_up + val_need_down) / 2
                        test_bs = list(current_x)
                        for i in p_indices: test_bs[i] = mid
                        _ = objective(test_bs)
                        
                        z_err = abs((target_z - current_metrics[0]) / target_z)
                        if z_err <= z_tol_percent:
                            current_x = test_bs
                            break
                            
                        curr_need_z_up = target_z > current_metrics[0]
                        curr_p_dir = get_param_z_dir(p_name, mid)
                        curr_need_param_up = (curr_need_z_up and curr_p_dir > 0) or (not curr_need_z_up and curr_p_dir < 0)
                        
                        if curr_need_param_up:
                            val_need_up = mid
                        else:
                            val_need_down = mid
                        current_x = test_bs
                            
                    if z_err <= z_tol_percent: break

            # Phase 2: Loss Optimization
            # Note: The prompt says "當進入loss優化後,阻抗tolerance就不再考慮是否符合"
            # It also says: "在開始loss優化時,判斷是否符合loss tolerance,如果符合loss tolerance則模擬結束"
            loss_err = abs((target_loss - current_metrics[1]) / abs(target_loss))
            if loss_err > loss_tol_percent:
                self.log(f"[{layer_name}] Phase 2: Loss Optimization")
                for p_name, p_keys in loss_params:
                    if iteration_count >= self.max_iter: break
                    p_indices = get_indices(p_keys)
                    if not p_indices: continue
                    p_idx = p_indices[0]
                    bound_min, bound_max = bounds[p_idx]
                    if bound_min == bound_max: continue # Variation = 0%
                        
                    loss_err = abs((target_loss - current_metrics[1]) / abs(target_loss))
                    if loss_err <= loss_tol_percent: break
                    
                    # Target depends on S21
                    need_s21_up = target_loss > current_metrics[1] # e.g. -2 > -3, need S21 to increase (less loss)
                    p_dir = get_param_s21_dir(p_name)
                    need_param_up = (need_s21_up and p_dir > 0) or (not need_s21_up and p_dir < 0)
                    
                    L_val = current_x[p_idx]
                    R_val = bound_max if need_param_up else bound_min
                    
                    # 1. Test Boundary
                    test_x = list(current_x)
                    for i in p_indices: test_x[i] = R_val
                    _ = objective(test_x)
                    
                    loss_err = abs((target_loss - current_metrics[1]) / abs(target_loss))
                    if loss_err <= loss_tol_percent:
                        current_x = test_x
                        break
                        
                    new_need_s21_up = target_loss > current_metrics[1]
                    new_need_param_up = (new_need_s21_up and p_dir > 0) or (not new_need_s21_up and p_dir < 0)
                    
                    if new_need_param_up == need_param_up:
                        self.log(f"[{layer_name}] {p_name} hit boundary, moving to next.")
                        current_x = test_x
                        continue
                        
                    # 2. Binary Search
                    self.log(f"[{layer_name}] {p_name} overshot, starting binary search.")
                    val_need_up = L_val if need_param_up else R_val
                    val_need_down = R_val if need_param_up else L_val
                    
                    for _ in range(10):
                        if iteration_count >= self.max_iter: break
                        mid = (val_need_up + val_need_down) / 2
                        test_bs = list(current_x)
                        for i in p_indices: test_bs[i] = mid
                        _ = objective(test_bs)
                        
                        loss_err = abs((target_loss - current_metrics[1]) / abs(target_loss))
                        if loss_err <= loss_tol_percent:
                            current_x = test_bs
                            break
                            
                        curr_need_s21_up = target_loss > current_metrics[1]
                        curr_need_param_up = (curr_need_s21_up and p_dir > 0) or (not curr_need_s21_up and p_dir < 0)
                        
                        if curr_need_param_up:
                            val_need_up = mid
                        else:
                            val_need_down = mid
                        current_x = test_bs
                            
                    if loss_err <= loss_tol_percent: break

            msg = "Optimization finished"
            success = True
        except Exception as e:
            msg = f"Optimization failed: {e}"
            success = False

        # Final stats update
        # Final stats update
        if success:
            stats['status'] = "Done" if best_error < 0.05 else "Max Iter" # Simple threshold
            if iteration_count >= self.max_iter: stats['status'] = "Max Iter"
            self.log(f"[{layer_name}] Finished. Best Z={best_metrics[0]:.2f}, Best Loss={best_metrics[1]:.2f}")
        else:
            stats['status'] = "Failed"
            self.log(f"[{layer_name}] Failed: {msg}")
        
        self.update_stats(layer_name, stats)
        
        return dict(zip(keys, best_x))
