import sys
import json
import os
from datetime import datetime
from pyedb import Edb

def format_float(val):
    return "{:.9f}".format(float(val)).rstrip('0').rstrip('.')

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def create_stackup_model(params):
    config = load_config()
    edb_version = config.get("edb_version", "2024.1")
    # Ensure output path is absolute or relative to cwd correctly
    edb = Edb(params["output_aedb_path"], version=edb_version)

    copper_cond = params.get("copper_conductivity", 5.8e7)
    edb.materials.add_conductor_material("my_copper", copper_cond)

    signal_half = params.get("signal_half", "top")

    # Pre-add all dielectric materials from the layers list
    for layer in params["layers"]:
        if layer["type"] == "dielectric":
            dk = format_float(layer.get("dk", 1))
            df = format_float(layer.get("df", 0))
            mat_name = f'm_{dk}_{df}'
            if mat_name not in edb.materials.materials:
                edb.materials.add_dielectric_material(name=mat_name, 
                                            permittivity=dk, 
                                            dielectric_loss_tangent=df)

    for i, layer in enumerate(params["layers"]):
        if layer["type"] == "signal":
            nodule_radius = layer.get("nodule_radius", "2um")
            surface_ratio = layer.get("hallhuray_surface_ratio", 0.2)
            
            fill_material = 'air'
            # The characterized dielectric is the one that fills the signal layer
            if signal_half == 'top' and i > 0:
                # Top half uses dielectric above for characterization
                prev_layer = params["layers"][i - 1]
                if prev_layer["type"] == "dielectric":
                    fill_material = f"m_{format_float(prev_layer.get('dk', 1))}_{format_float(prev_layer.get('df', 0))}"
            elif signal_half == 'bottom' and i < len(params["layers"]) - 1:
                # Bottom half uses dielectric below for characterization
                next_layer = params["layers"][i + 1]
                if next_layer["type"] == "dielectric":
                    fill_material = f"m_{format_float(next_layer.get('dk', 1))}_{format_float(next_layer.get('df', 0))}"
            elif signal_half == 'mid' or True:
                # Fallback: search for nearest
                if i > 0 and params["layers"][i-1]['type'] == 'dielectric':
                     l_data = params["layers"][i-1]
                     fill_material = f"m_{format_float(l_data.get('dk', 1))}_{format_float(l_data.get('df', 0))}"
                elif i < len(params["layers"]) - 1 and params["layers"][i+1]['type'] == 'dielectric':
                     l_data = params["layers"][i+1]
                     fill_material = f"m_{format_float(l_data.get('dk', 1))}_{format_float(l_data.get('df', 0))}"

            signal_layer = edb.stackup.add_layer(layer_name=layer["layername"],
                                                 method="add_on_bottom",
                                                 layer_type='signal',
                                                 thickness=layer["thickness"],
                                                 material="my_copper",
                                                 fillMaterial=fill_material,
                                                 etch_factor=layer.get("etch_factor", 1.0),
                                                 enable_roughness=True) 
            
            signal_layer.top_hallhuray_nodule_radius = nodule_radius
            signal_layer.top_hallhuray_surface_ratio = surface_ratio
            signal_layer.bottom_hallhuray_nodule_radius = nodule_radius
            signal_layer.bottom_hallhuray_surface_ratio = surface_ratio
            signal_layer.side_hallhuray_nodule_radius = nodule_radius
            signal_layer.side_hallhuray_surface_ratio = surface_ratio
        
        elif layer["type"] == "dielectric":
            dk = format_float(layer["dk"])
            df = format_float(layer["df"])
            mat_name = f'm_{dk}_{df}'
            
            edb.stackup.add_layer(layer_name=layer["layername"],
                                  method="add_on_bottom",
                                  layer_type='dielectric',
                                  thickness=layer["thickness"],
                                  material=mat_name)
            
    spacing_mil = params["trace_params"]['spacing_mil']
    width_mil = params["trace_params"]['width_mil']

    line_p = edb.modeler.create_trace([('0mil', f'{(spacing_mil+width_mil)/2}mil'), ('1000mil', f'{(spacing_mil+width_mil)/2}mil')], 
                                        width=f'{width_mil}mil',
                                        net_name='pos',
                                        layer_name=params["target_layer"],
                                        start_cap_style='Flat',
                                        end_cap_style='Flat')
    line_n = edb.modeler.create_trace([('0mil', f'{-(spacing_mil+width_mil)/2}mil'), ('1000mil', f'{-(spacing_mil+width_mil)/2}mil')],
                                        width=f'{width_mil}mil',
                                        net_name='neg',
                                        layer_name=params["target_layer"],
                                        start_cap_style='Flat',
                                        end_cap_style='Flat')

    for layername in params["ref_layers"]:
        edb.modeler.create_rectangle(layer_name=layername, 
                                net_name='GND',
                                lower_left_point=('0mil', '-50mil'),
                                upper_right_point=('1000mil', '50mil')
                                )
                                                   

    edb.hfss.create_differential_wave_port(line_p, line_p.center_line[0], line_n, line_n.center_line[0], port_name='port1')
    edb.hfss.create_differential_wave_port(line_p, line_p.center_line[-1], line_n, line_n.center_line[-1], port_name='port2')
    #edb.excitations['port1'].deembed = True
    #edb.excitations['port1'].deembed_length = '-990mil'

    setup = edb.create_hfss_setup()
    setup.set_solution_single_frequency(frequency=f'{params["frequency"]}GHz', 
                                        max_num_passes=20, 
                                        max_delta_s=params.get("max_delta_s", 0.02))

    freq_stop = params.get("freq_stop", 5)
    frequency_range = [["linear scale", "50MHz", f"{freq_stop}GHz", '50MHz']]                                        
    setup.add_sweep('sweep', frequency_set=frequency_range)


    edb.save()
    edb.close_edb()

def create_full_stackup(params):
    output_path = params["output_aedb_path"]
    stackup_data = params["stackup_data"]
    
    config = load_config()
    edb_version = config.get("edb_version", "2024.1")
    
    edb = Edb(output_path, version=edb_version)
    
    copper_cond = params.get("copper_conductivity", 5.8e7)
    edb.materials.add_conductor_material("my_copper", copper_cond)
    
    # Pre-add all dielectric materials
    for layer in stackup_data['rows']:
        if layer['type'] == 'dielectric':
            dk = format_float(layer.get('dk', 1))
            df = format_float(layer.get('df', 0))
            mat_name = f'm_{dk}_{df}'
            if mat_name not in edb.materials.materials:
                edb.materials.add_dielectric_material(name=mat_name, permittivity=dk, dielectric_loss_tangent=df)

    signal_indices = [idx for idx, l in enumerate(stackup_data['rows']) if l['type'] == 'conductor']
    midpoint = len(signal_indices) // 2
    
    current_signal_count = 0
    for i, layer in enumerate(stackup_data['rows']):
        layer_name = layer['layername']
        layer_type = layer['type']
        thickness = f"{layer['thickness']}mil"
        
        if layer_type == 'conductor':
            material = "my_copper"
            etch_factor = float(layer.get('etchfactor', 0))
            surface_ratio = float(layer.get('hallhuray_surface_ratio', 0))
            nodule_radius = f"{layer.get('nodule_radius', 0)}um"
            
            half = "top" if current_signal_count < midpoint else "bottom"
            current_signal_count += 1
            
            fill_material = 'air'
            if half == 'top':
                 # During characterization of top layers, the dielectric above is the one varied/used.
                 # Search upwards for nearest dielectric to use as fill.
                for j in range(i - 1, -1, -1):
                    if stackup_data['rows'][j]['type'] == 'dielectric':
                        l_data = stackup_data['rows'][j]
                        fill_material = f"m_{format_float(l_data.get('dk', 1))}_{format_float(l_data.get('df', 0))}"
                        break
            else:
                # During characterization of bottom layers, the dielectric below is the one varied/used.
                # Search downwards for nearest dielectric to use as fill.
                for j in range(i + 1, len(stackup_data['rows'])):
                    if stackup_data['rows'][j]['type'] == 'dielectric':
                        l_data = stackup_data['rows'][j]
                        fill_material = f"m_{format_float(l_data.get('dk', 1))}_{format_float(l_data.get('df', 0))}"
                        break

            signal_layer = edb.stackup.add_layer(layer_name=layer_name,
                                                 method="add_on_bottom",
                                                 layer_type='signal',
                                                 thickness=thickness,
                                                 material=material,
                                                 fillMaterial=fill_material,
                                                 etch_factor=etch_factor,
                                                 enable_roughness=True)
            
            signal_layer.top_hallhuray_nodule_radius = nodule_radius
            signal_layer.top_hallhuray_surface_ratio = surface_ratio
            signal_layer.bottom_hallhuray_nodule_radius = nodule_radius
            signal_layer.bottom_hallhuray_surface_ratio = surface_ratio
            signal_layer.side_hallhuray_nodule_radius = nodule_radius
            signal_layer.side_hallhuray_surface_ratio = surface_ratio
            
        elif layer_type == 'dielectric':
            dk = format_float(layer.get('dk', 1))
            df = format_float(layer.get('df', 0))
            mat_name = f'm_{dk}_{df}'
            
            edb.stackup.add_layer(layer_name=layer_name,
                                  method="add_on_bottom",
                                  layer_type='dielectric',
                                  thickness=thickness,
                                  material=mat_name)

    edb.save()
    edb.stackup.export(f'{params["output_aedb_path"]}/full_stackup.xml', include_material_with_layer=True)

    edb.close_edb()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        with open(json_path, 'r') as f:
            params = json.load(f)
            
        if params.get("mode") == "full_stackup":
            create_full_stackup(params)
        else:
            create_stackup_model(params)
    else:
        # Default for testing
        pass