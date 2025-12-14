import sys
import json
import os
from ansys.aedt.core import Hfss3dLayout 

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def run_simulation(edb_path):
    config = load_config()
    aedt_version = config.get("aedt_version", "2025.2")
    
    hfss = Hfss3dLayout(edb_path, version=aedt_version, non_graphical=True, remove_lock=True)

    hfss.set_differential_pair('port1:T1', 'port1:T2', 'comm1', 'diff1')
    hfss.set_differential_pair('port2:T1', 'port2:T2', 'comm2', 'diff2')

    hfss.analyze(cores=4)
    data = hfss.post.get_solution_data('re(S(diff1,diff1))', context="Differential Pairs")
    s11 = data.data_real()[0]
    zdiff = 100 * (1 + s11) / (1 - s11)

    data = hfss.post.get_solution_data('dB(S(diff2,diff1))', context="Differential Pairs")
    dbs21 = data.data_real()[0] 

    print(f"RESULT: {zdiff}, {dbs21}")
    hfss.release_desktop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        edb_path = sys.argv[1]
    else:
        # Default for testing/fallback
        edb_path = r"D:\OneDrive - ANSYS, Inc\a-client-repositories\quanta-stackup-characterization-202510\stackup characterization\tmp\20251127_121842.aedb"
    
    run_simulation(edb_path)
