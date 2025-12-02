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
def get_signal_layers(stackup_data):
    signal_layers = []
    for i, layer in enumerate(stackup_data['rows']):
        if layer['type'] == 'conductor' and layer.get('width') and layer.get('spacing'):
            signal_layers.append(i)
    return signal_layers

def extract_layer_params(stackup_data, layer_index):
    rows = stackup_data['rows']
    layer = rows[layer_index]
    diel_above_idx = layer_index - 1
    diel_below_idx = layer_index + 1
    
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
            d['dk'] = float(l_data.get('dk', 1))
            d['df'] = float(l_data.get('df', 0))
            
            if override_params:
                if 'dk' in override_params: d['dk'] = override_params['dk']
                if 'df' in override_params: d['df'] = override_params['df']
        
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
        "target_layer": layer['layername'],
        "trace_params": trace_params,
        "ref_layers": ref_layers_list,
        "layers": model_layers
    }

def save_json(data, json_path):
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

class CharacterizationEngine:
    def __init__(self, json_data, max_iter, log_callback=None, stats_callback=None):
        self.data = json_data
        self.max_iter = max_iter
        self.log_callback = log_callback
        self.stats_callback = stats_callback
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(os.getcwd(), f"stackup_characterization_{ts}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.log_file = os.path.join(self.output_dir, "characterization_log.csv")
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["iteration", "layer", "width", "spacing", "thickness", "etch_factor", "dk_up", "dk_down", "df_up", "df_down", "Zdiff", "S21", "pass?"])

    def log(self, msg):
        print(msg)
        if self.log_callback:
            self.log_callback(msg)

    def update_stats(self, layer_name, stats):
        if self.stats_callback:
            self.stats_callback(layer_name, stats)

    def run(self):
        self.log(f"Starting characterization. Output dir: {self.output_dir}")
        signal_indices = get_signal_layers(self.data)
        self.log(f"Found {len(signal_indices)} signal layers to characterize.")
        
        for idx in signal_indices:
            optimized_params = self.optimize_layer(idx)
            
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
            "stackup_data": self.data
        }
        temp_full_path = os.path.join(self.output_dir, "full_stackup_params.json")
        save_json(full_stackup_params, temp_full_path)
        
        try:
            subprocess.run([sys.executable, "modeling.py", temp_full_path], check=True)
            self.log(f"Full stackup created at {full_aedb_path}")
        except Exception as e:
            self.log(f"Failed to create full stackup: {e}")

        self.log(f"Characterization complete. Saved to {final_json_path}")

    def optimize_layer(self, layer_index):
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

        # Tracking best
        best_error = float('inf')
        best_x = x0
        best_metrics = (0, 0) # z, loss
        
        iteration_count = 0

        def objective(x):
            nonlocal iteration_count, best_error, best_x, best_metrics
            
            # Check max iter
            if iteration_count >= self.max_iter:
                # Force stop by raising error or returning huge value?
                # Scipy minimize doesn't stop easily.
                # We can just return best_error to discourage moving?
                # Or raise StopIteration?
                # Let's just return a large value, but we need to ensure we don't overwrite best.
                return best_error + 1000 

            iteration_count += 1
            current_vals = dict(zip(keys, x))
            
            # Temp files
            temp_params_path = os.path.join(self.output_dir, f"params_{layer_name}_{iteration_count}.json")
            aedb_path = os.path.join(self.output_dir, f"sim_{layer_name}_{iteration_count}.aedb")
            
            modeling_params = create_modeling_params(self.data, layer_info, current_vals, aedb_path)
            save_json(modeling_params, temp_params_path)
            
            # Run Modeling
            self.log(f"[{layer_name}] Iter {iteration_count}: Modeling...")
            subprocess.run([sys.executable, "modeling.py", temp_params_path], check=True)
            
            # Run Simulation
            self.log(f"[{layer_name}] Iter {iteration_count}: Simulating...")
            result = subprocess.run([sys.executable, "simulation.py", aedb_path], capture_output=True, text=True, check=True)
            
            zdiff = 0
            dbs21 = 0
            for line in result.stdout.splitlines():
                if line.startswith("RESULT:"):
                    parts = line.split(":")[1].split(",")
                    zdiff = float(parts[0])
                    dbs21 = float(parts[1])
                    break
            
            self.log(f"[{layer_name}] Iter {iteration_count}: Zdiff={zdiff:.2f}, S21={dbs21:.2f}")
            
            z_error = abs(zdiff - target_z) / target_z
            loss_error = abs(dbs21 - target_loss) / abs(target_loss)
            total_error = z_error + loss_error
            
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
            
            return total_error

        # Run optimization
        # We set maxiter in options, but also handle it in objective
        try:
            res = minimize(objective, x0, bounds=bounds, method='Nelder-Mead', tol=0.01, options={'maxiter': self.max_iter})
            success = res.success
            msg = "Optimization converged" if success else "Max iterations reached or failed"
        except Exception as e:
            msg = f"Optimization failed: {e}"
            success = False

        # Final stats update
        stats['status'] = "Done" if best_error < 0.05 else "Max Iter" # Simple threshold
        if iteration_count >= self.max_iter: stats['status'] = "Max Iter"
        
        self.update_stats(layer_name, stats)
        self.log(f"[{layer_name}] Finished. Best Z={best_metrics[0]:.2f}, Best Loss={best_metrics[1]:.2f}")
        
        return dict(zip(keys, best_x))
