from ansys.aedt.core import Hfss3dLayout 
edb_path = r"D:\OneDrive - ANSYS, Inc\a-client-repositories\quanta-stackup-characterization-202510\stackup characterization\tmp\20251127_121842.aedb"

hfss = Hfss3dLayout(edb_path, version='2025.2', remove_lock=True)


hfss.set_differential_pair('port1:T1', 'port1:T2', 'comm1', 'diff1')
hfss.set_differential_pair('port2:T1', 'port2:T2', 'comm2', 'diff2')

hfss.analyze(cores=4)
data = hfss.post.get_solution_data('mag(S(diff1,diff1))', context="Differential Pairs")
s11 = data.data_real()[0]
zdiff = 100 * (1 + s11) / (1 - s11)

data = hfss.post.get_solution_data('dB(S(diff2,diff1))', context="Differential Pairs")
dbs21 = data.data_real()[0]

print(zdiff, dbs21)
hfss.release_desktop()
