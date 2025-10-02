import os
import json
from pyaedt import Hfss3dLayout

file_path = "data/pcb.aedt"

try:
    os.remove(file_path)
    print(f"已刪除檔案: {file_path}")
except FileNotFoundError:
    print("檔案不存在")
except PermissionError:
    print("沒有刪除權限")


hfss = Hfss3dLayout('data/pcb.aedb', version='2025.1')

hfss.set_differential_pair('port1:T1', 
                           'port1:T2',
                           'comm1',
                           'diff1')


hfss.set_differential_pair('port2:T1', 
                           'port2:T2',
                           'comm1',
                           'diff2')

excitation = hfss.excitation_objects['port1:T1']
excitation.properties['Deembed'] = True
excitation.properties['Deembed Distance'] = '-900mil'
hfss.analyze()


data = hfss.post.get_solution_data('dB(S(diff2,diff1))',
                                   context="Differential Pairs")
x = data.data_real()[0]
with open('data/result.json', 'w') as f:
    json.dump(x, f)

hfss.release_desktop()
