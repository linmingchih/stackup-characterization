import json
import shutil
from pathlib import Path
from pyedb import Edb

edb = Edb(version='2026.1', grpc=False)

#%% Add materials
copper_cond = 6.7e7
edb.materials.add_conductor_material("my_copper", copper_cond)

dk_up = "3.73"
df_up = "0.019"
mat_up = f"m_{dk_up}_{df_up}"
if mat_up not in edb.materials.materials:
    edb.materials.add_dielectric_material(
        name=mat_up,
        permittivity=dk_up,
        dielectric_loss_tangent=df_up,
    )

dk_down = "4.14"
df_down = "0.015"
mat_down = f"m_{dk_down}_{df_down}"
if mat_down not in edb.materials.materials:
    edb.materials.add_dielectric_material(
        name=mat_down,
        permittivity=dk_down,
        dielectric_loss_tangent=df_down,
    )

#%% Add stackup layers
gnd_layer = edb.stackup.add_layer(
    layer_name="GND1",
    method="add_on_bottom",
    layer_type="signal",
    thickness="2.1mil",
    material="my_copper",
    filling_material="air",
    etch_factor=0,
    enable_roughness=True,
)

gnd_layer = edb.stackup.layers['GND1']
gnd_layer.top_hallhuray_nodule_radius = "0um"
gnd_layer.top_hallhuray_surface_ratio = 0
gnd_layer.bottom_hallhuray_nodule_radius = "0um"
gnd_layer.bottom_hallhuray_surface_ratio = 0
gnd_layer.side_hallhuray_nodule_radius = "0um"
gnd_layer.side_hallhuray_surface_ratio = 0

edb.stackup.add_layer(
    layer_name="UNNAMED_005",
    method="add_on_bottom",
    layer_type="dielectric",
    thickness="2.36mil",
    material=mat_up,
)

signal_layer = edb.stackup.add_layer(
    layer_name="IN1",
    method="add_on_bottom",
    layer_type="signal",
    thickness="0.6mil",
    material="my_copper",
    filling_material=mat_down,
    etch_factor=-2.5,
    enable_roughness=True,
)
signal_layer = edb.stackup.layers["IN1"]

signal_layer.top_hallhuray_nodule_radius = "0.5um"
signal_layer.top_hallhuray_surface_ratio = 2.9
signal_layer.bottom_hallhuray_nodule_radius = "0.5um"
signal_layer.bottom_hallhuray_surface_ratio = 2.9
signal_layer.side_hallhuray_nodule_radius = "0.5um"
signal_layer.side_hallhuray_surface_ratio = 2.9

edb.stackup.add_layer(
    layer_name="UNNAMED_007",
    method="add_on_bottom",
    layer_type="dielectric",
    thickness="10mil",
    material=mat_down,
)

vcc_layer = edb.stackup.add_layer(
    layer_name="VCC",
    method="add_on_bottom",
    layer_type="signal",
    thickness="1.2mil",
    material="my_copper",
    filling_material="air",
    etch_factor=0,
    enable_roughness=True,
)

vcc_layer = edb.stackup.layers["VCC"]

vcc_layer.top_hallhuray_nodule_radius = "0um"
vcc_layer.top_hallhuray_surface_ratio = 0
vcc_layer.bottom_hallhuray_nodule_radius = "0um"
vcc_layer.bottom_hallhuray_surface_ratio = 0
vcc_layer.side_hallhuray_nodule_radius = "0um"
vcc_layer.side_hallhuray_surface_ratio = 0

#%% Create traces
spacing_mil = 2.99
width_mil = 10.0

line_p = edb.modeler.create_trace(
    [("0mil", f"{(spacing_mil + width_mil) / 2}mil"), ("1000mil", f"{(spacing_mil + width_mil) / 2}mil")],
    width=f"{width_mil}mil",
    net_name="pos",
    layer_name="IN1",
    start_cap_style="Flat",
    end_cap_style="Flat",
)

line_n = edb.modeler.create_trace(
    [("0mil", f"{-(spacing_mil + width_mil) / 2}mil"), ("1000mil", f"{-(spacing_mil + width_mil) / 2}mil")],
    width=f"{width_mil}mil",
    net_name="neg",
    layer_name="IN1",
    start_cap_style="Flat",
    end_cap_style="Flat",
)

#%% Create reference planes
gnd_rect = edb.modeler.create_rectangle(
    layer_name="GND",
    net_name="GND",
    lower_left_point=("0mil", "-50mil"),
    upper_right_point=("1000mil", "50mil"),
)

vcc_rect = edb.modeler.create_rectangle(
    layer_name="VCC",
    net_name="GND",
    lower_left_point=("0mil", "-50mil"),
    upper_right_point=("1000mil", "50mil"),
)

#%% Create ports
port1 = edb.excitation_manager.create_differential_wave_port(
    line_p,
    line_p.center_line[0],
    line_n,
    line_n.center_line[0],
    port_name="port1",
)

port2 = edb.excitation_manager.create_differential_wave_port(
    line_p,
    line_p.center_line[-1],
    line_n,
    line_n.center_line[-1],
    port_name="port2",
)



#%% Create HFSS setup and sweep
setup = edb.simulation_setups.create()

setup.set_solution_single_frequency(
    frequency="4GHz",
    max_num_passes=20,
    max_delta_s=0.02,
)

frequency_range = [["linear scale", "50MHz", "5GHz", "50MHz"]]
setup.add_sweep("sweep", frequency_set=frequency_range)

#%% Save, export, and close
edb.save_as('d:/demo/test3.aedb')

edb.close()

