import sys
import json
import os
from datetime import datetime
from pyedb import Edb

def create_stackup_model(params):
    if os.path.isdir(params["output_aedb_path"]):
        # shutil.rmtree(params["output_aedb_path"], ignore_errors=True) # os.rmdir only works for empty dirs
        # For safety, let's just let Edb handle it or assume it's a new path. 
        # The original code used os.rmdir which might fail if not empty.
        # Let's stick to original logic but maybe safer? 
        # Edb(..., overwrite=True) is better if available, but let's stick to the script.
        pass

    # Ensure output path is absolute or relative to cwd correctly
    edb = Edb(params["output_aedb_path"], version='2024.1')

    for layer in params["layers"]:
        if layer["type"] == "signal":
            nodule_radius = layer.get("nodule_radius", "2um")
            surface_ratio = layer.get("hallhuray_surface_ratio", 0.2)
            
            signal_layer = edb.stackup.add_layer(layer_name=layer["layername"],
                                                 method="add_on_bottom",
                                                 layer_type='signal',
                                                 thickness=layer["thickness"],
                                                 material=layer["material"],
                                                 etch_factor=layer.get("etch_factor", 1.0),
                                                 enable_roughness=True) 
            
            signal_layer.top_hallhuray_nodule_radius = nodule_radius
            signal_layer.top_hallhuray_surface_ratio = surface_ratio
            signal_layer.bottom_hallhuray_nodule_radius = nodule_radius
            signal_layer.bottom_hallhuray_surface_ratio = surface_ratio
            signal_layer.side_hallhuray_nodule_radius = nodule_radius
            signal_layer.side_hallhuray_surface_ratio = surface_ratio
        
        elif layer["type"] == "dielectric":
            dk = layer["dk"]
            df = layer["df"]
            if f'm_{dk}_{df}' not in edb.materials.materials:
                edb.materials.add_dielectric_material(name=f'm_{dk}_{df}', 
                                            permittivity=dk, 
                                            dielectric_loss_tangent=df)
            
            edb.stackup.add_layer(layer_name=layer["layername"],
                                  method="add_on_bottom",
                                  layer_type='dielectric',
                                  thickness=layer["thickness"],
                                  material=f'm_{dk}_{df}')
            
    spacing_mil = params["trace_params"]['spacing_mil']
    width_mil = params["trace_params"]['width_mil']

    line_p = edb.modeler.create_trace([('0mil', f'{(spacing_mil+width_mil)/2}mil'), ('100mil', f'{(spacing_mil+width_mil)/2}mil')], 
                                        width=f'{width_mil}mil',
                                        net_name='pos',
                                        layer_name=params["target_layer"],
                                        start_cap_style='Flat',
                                        end_cap_style='Flat')
    line_n = edb.modeler.create_trace([('0mil', f'{-(spacing_mil+width_mil)/2}mil'), ('100mil', f'{-(spacing_mil+width_mil)/2}mil')],
                                        width=f'{width_mil}mil',
                                        net_name='neg',
                                        layer_name=params["target_layer"],
                                        start_cap_style='Flat',
                                        end_cap_style='Flat')

    for layername in params["ref_layers"]:
        edb.modeler.create_rectangle(layer_name=layername, 
                                net_name='GND',
                                lower_left_point=('0mil', '-50mil'),
                                upper_right_point=('100mil', '50mil')
                                )
                                                   

    edb.hfss.create_differential_wave_port(line_p, line_p.center_line[0], line_n, line_n.center_line[0], port_name='port1')
    edb.hfss.create_differential_wave_port(line_p, line_p.center_line[-1], line_n, line_n.center_line[-1], port_name='port2')
    edb.excitations['port1'].deembed = True
    edb.excitations['port1'].deembed_length = '-900mil'

    setup = edb.create_hfss_setup()
    setup.set_solution_single_frequency(frequency=f'{params["frequency"]}GHz', 
                                        max_num_passes=20, 
                                        max_delta_s=0.01)


    edb.save()
    edb.close_edb()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        with open(json_path, 'r') as f:
            params = json.load(f)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        params = {
            "output_aedb_path": f'tmp/{ts}.aedb',
            "frequency": 5.0,
            "target_layer": "top",
            "trace_params": {
                "width_mil": 5,
                "spacing_mil": 6
            },
            "ref_layers": ["gnd1"],
            "layers": [
                {
                    "layername": "top",
                    "type": "signal",
                    "thickness": "1.2mil",
                    "material": "copper",
                    "etch_factor": -2.5,
                    "hallhuray_surface_ratio": 0.5,
                    "nodule_radius": "0.5um",

                },
                {
                    "layername": "diel1",
                    "type": "dielectric",
                    "thickness": "3mil",
                    "dk": 4.0,
                    "df": 0.02
                },
                {
                    "layername": "gnd1",
                    "type": "signal",
                    "thickness": "1.2mil",
                    "material": "copper",
                    "etch_factor": -2.5,
                    "hallhuray_surface_ratio": 0.5,
                    "nodule_radius": "0.5um",
                }
            ]
        }
    
    create_stackup_model(params)