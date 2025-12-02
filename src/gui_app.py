import webview
import threading
import json
import os
import sys
import time
from characterization_engine import CharacterizationEngine

class StackupAPI:
    def __init__(self):
        self.window = None
        self.engine = None
        self.running = False
        self.stats = {}

    def set_window(self, window):
        self.window = window

    def select_file(self):
        file_types = ('JSON Files (*.json)', 'All files (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        return result[0] if result else None

    def start_optimization(self, json_path, max_iter):
        if self.running:
            return {"status": "error", "message": "Optimization already running"}
        
        if not json_path or not os.path.exists(json_path):
            return {"status": "error", "message": "Invalid file path"}

        try:
            max_iter = int(max_iter)
        except ValueError:
            return {"status": "error", "message": "Invalid max iterations value"}

        self.running = True
        self.stats = {} # Reset stats
        
        # Load JSON
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                json_data = json.load(f)
        except Exception as e:
            self.running = False
            return {"status": "error", "message": f"Failed to load JSON: {str(e)}"}

        # Start thread
        thread = threading.Thread(target=self._run_engine, args=(json_data, max_iter, json_path))
        thread.daemon = True
        thread.start()
        
        return {"status": "success", "message": "Optimization started"}

    def _run_engine(self, json_data, max_iter, original_path):
        def log_callback(msg):
            if self.window:
                # Escape quotes for JS
                clean_msg = msg.replace("'", "\\'").replace('"', '\\"').replace('\n', '<br>')
                self.window.evaluate_js(f"addLog('{clean_msg}')")

        def stats_callback(layer_name, layer_stats):
            self.stats[layer_name] = layer_stats
            if self.window:
                self.window.evaluate_js(f"updateStats('{layer_name}', {json.dumps(layer_stats)})")

        try:
            # Determine output directory based on original file
            output_base_dir = os.path.dirname(original_path)
            
            self.engine = CharacterizationEngine(json_data, max_iter, log_callback, stats_callback, output_base_dir=output_base_dir)
            self.engine.run()
            
            log_callback("Optimization Process Completed.")
            if self.window:
                self.window.evaluate_js("optimizationComplete()")
                
        except Exception as e:
            log_callback(f"Error during optimization: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def get_statistics(self):
        return self.stats

    def load_file_info(self, json_path):
        if not json_path or not os.path.exists(json_path):
             return {"status": "error", "message": "File not found"}
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # We need get_signal_layers from characterization_engine, but it's not imported as a function
            # It's a helper in characterization_engine.py. Let's import it.
            from characterization_engine import get_signal_layers
            signal_indices = get_signal_layers(data)
            layers = []
            for idx in signal_indices:
                layer = data['rows'][idx]
                layers.append({
                    "name": layer['layername'],
                    "target_z": float(layer.get('impedance_target', 0)),
                    "target_loss": float(layer.get('loss_target', 0))
                })
            return {"status": "success", "layers": layers}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_config(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "..", "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {"aedt_version": "2025.2", "edb_version": "2024.1"}

    def save_config(self, config_data):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "..", "config.json")
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            return {"status": "success", "message": "Configuration saved"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def main():
    api = StackupAPI()
    
    # Get absolute path to templates/index.html
    # Assuming run from project root
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html')
    if not os.path.exists(template_path):
        # Fallback if running from different dir?
        # Try to find it relative to cwd
        template_path = os.path.join(os.getcwd(), 'templates', 'index.html')

    window = webview.create_window('Stackup Characterization Tool', url=template_path, js_api=api, width=1000, height=800)
    api.set_window(window)
    webview.start(debug=False)

if __name__ == '__main__':
    main()
