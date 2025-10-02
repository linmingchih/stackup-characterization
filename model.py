from pyedb import Edb


def mil_to_meter(value_mil: float) -> float:
    """
    將 mil (thousandth of an inch) 轉換成 meter。
    
    1 mil = 2.54e-5 meter
    """
    return value_mil * 2.54e-5



edb = Edb(version='2024.1', control_file='data/input_stk.xml')


dir(edb)
edb.stackup.load('data/input_stk.xml')
#edb.import_material_from_control_file('data/input_stk.xml')
print(edb.stackup.signal_layers.items())


setup = edb.hfss.add_setup()
#sweep = setup.add_frequency_sweep()

edb.save_edb_as('tmp/pcb.aedb')

#%%
width = 2
pitch = 3
length = 100
signal_layers = []
for layer_name, layer in edb.stackup.signal_layers.items():
    signal_layers.append((layer_name, layer))

for n, (layer_name, layer) in enumerate(signal_layers):
    if layer_name == 'L4_IN2':
        pos = edb.modeler.create_trace([(0, f'{pitch/2}mil'), (f'{length}mil', f'{pitch/2}mil')], 
                                       layer_name, 
                                       width=mil_to_meter(width),
                                       net_name='pos',
                                       start_cap_style="Flat",
                                       end_cap_style="Flat",)
    
        neg = edb.modeler.create_trace([(0, f'-{pitch/2}mil'), (f'{length}mil', f'-{pitch/2}mil')], 
                                       layer_name, 
                                       width=mil_to_meter(width),
                                       net_name='neg',
                                       start_cap_style="Flat",
                                       end_cap_style="Flat",)
        
        edb.modeler.create_rectangle(layer_name = signal_layers[n-1][0],
                                     net_name='GND',
                                     lower_left_point=('0mil', '-10mil'), 
                                     upper_right_point=(f'{length}mil', '10mil'))
        
        edb.modeler.create_rectangle(layer_name = signal_layers[n+1][0],
                                     net_name='GND',
                                     lower_left_point=('0mil', '-10mil'), 
                                     upper_right_point=(f'{length}mil', '10mil'))
        
        edb.hfss.create_differential_wave_port(pos, 
                                               (0, f'{pitch/2}mil'), 
                                               neg, 
                                               (0, f'-{pitch/2}mil'),
                                               port_name='port1')

        edb.hfss.create_differential_wave_port(pos, 
                                               (f'{length}mil', f'{pitch/2}mil'), 
                                               neg, 
                                               (f'{length}mil', f'-{pitch/2}mil'),
                                               port_name='port2')
                


        edb.save_edb_as('tmp/pcb.aedb')
        edb.close_edb()

                
        break