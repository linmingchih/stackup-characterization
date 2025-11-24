# Stackup Characterization Tool — Full Technical Prompt

## 1. Purpose

The tool automates stackup characterization in ANSYS HFSS 3D Layout using PyEDB for stackup/geometry creation, PyAEDT for HFSS simulation, and SciPy for iterative optimization. It ingests a JSON exported from `stackup_viewer.html`, adjusts parameters, generates `.aedb` projects, runs simulations, extracts Zdiff/S21, and produces characterized JSON and XML outputs.

---

## 2. JSON Specification (based on uploaded file)

The JSON structure:

```json
{
  "frequency": 5,
  "settings": { ... },
  "rows": [ ... ]
}
```

### 2.1 `frequency`

Unit: GHz. Controls the HFSS setup frequency in `modeling.py`.

### 2.2 `settings.variation`

Maximum parameter variation (percent), used to clamp adjustments during optimization:

- etchfactor: ±20%
- thickness: ±20%
- dk: ±20%
- df: ±20%
- hallhuray_surface_ratio: ±50%
- nodule_radius: ±50%

### 2.3 `settings.tolerance`

```
impedance_target.tolerance = 1%
loss_target.tolerance      = 1%
```

Zdiff and dB(S21) must each fall within `target_value ± 1%`.

### 2.4 `rows[]` layer definitions

Each row includes:

- `layername`
- `type`: `"conductor"` or `"dielectric"`
- `reference_layers`: `"layerA / layerB"`
- Conductor parameters: `width`, `spacing`, `etchfactor`, `thickness`, `hallhuray_surface_ratio`, `nodule_radius`
- Dielectric parameters: `dk`, `df`, `thickness`
- Targets: `impedance_target`, `loss_target`

Signal layers are conductors with both `width` and `spacing` defined (for example `top`, `in1`, `in4`) and require Zdiff and loss characterization. Conductor layers without width/spacing are planes (for example `gnd1`, `gnd2`, `gnd3`, `gnd4`) and serve as references.

#### Reference layer rules

- `"A / B"`: A is the top reference, B is the bottom reference.
- `"None / X"`: single reference on bottom.
- `"X / None"`: single reference on top.

Examples from the JSON: `top` → `None / gnd1`, `in1` → `gnd1 / gnd2`, `in4` → `gnd3 / gnd4`, `bot` → `gnd4 / None`. These determine dielectric inclusion above/below, reference planes, and wave port references.

---

## 3. MVC Architecture

- **Model:** `characterization_process.py`, `modeling.py`, `simulation.py`
- **View:** `gui.py` (pywebview)
- **Controller:** `main.py`

---

## 4. Script Behavior

### 4.1 `main.py`

- Initializes the GUI and version info.
- Sends the input JSON path to the characterization process.
- Receives and prints real-time messages.

### 4.2 `gui.py`

- Pywebview-based GUI.
- File picker to choose the exported JSON.
- Start button to launch characterization.
- Information panel that streams messages from modeling and simulation subprocesses (pywebview).

### 4.3 `characterization_process.py` (core logic)

**Pre-run:** Create a timestamped folder next to the JSON to hold `.aedb` and outputs, for example:

```
my_stackup/
  stackup_layers_1007.json
  20251124_153050/  # AEDB and outputs live here
```

**Workflow per signal layer:**

1. Identify signal layers (`type == "conductor"` and both `width` and `spacing` set).
2. Extract initial parameters: width, spacing, etchfactor, thickness, hallhuray_surface_ratio, nodule_radius; dielectric thickness/dk/df above and below.
3. Prepare modeling parameters using the dielectric layers immediately above and below (physical ordering).
4. Create `.aedb` via `modeling.py` (subprocess) with layer geometry, dielectric stack, reference layers, frequency, and variables.
5. Run HFSS via `simulation.py` (subprocess); extract Zdiff and dB(S21).
6. Evaluate against targets (`target ± tolerance`); if out of range, adjust parameters and iterate.

### 4.4 Parameter adjustment priority

Adjustment order (clamped by variation limits):

1. etch_factor (±20%)
2. conductor thickness (±20%)
3. dielectric Dk above/below (±20%)
4. dielectric Df above/below (±20%)
5. Hallhuray surface ratio (±50%)
6. nodule radius (±50%)

Each parameter stays within `original_value ± variation%`.

### 4.5 CSV logging

Log columns:

| iteration | layer | width | spacing | thickness | etch_factor | dk_up | dk_down | df_up | df_down | Zdiff | S21 | pass? |
| --------- | ----- | ----- | ------- | --------- | ----------- | ----- | ------- | ----- | ------- | ----- | --- | ----- |

### 4.6 Final output

For all completed signal layers, save:

- `stackup_layers_1007_ok.json`
- `stackup_layers_1007_ok.csv`
- `stackup_layers_1007_ok.xml`

Final XML is regenerated via PyEDB using optimized parameters.

---

## 5. `modeling.py` behavior

- Receives JSON-derived parameters.
- Uses PyEDB (not PyAEDT) to build the full stackup, differential pair on the target layer, dielectrics above/below, and conductor reference layers.
- Creates differential wave ports with correct reference elevation.
- Creates HFSS setup at `frequency` GHz and saves the `.aedb`.

Note: PyEDB runs separately because PyAEDT initialization in the same process fails.

Example PyEDB code snippet for `modeling.py`:
```python
from pyedb import Edb

edb = Edb(version='2024.1')

edb.materials.add_dielectric_material(name='up_epoxy', 
                                      permittivity=4, 
                                      dielectric_loss_tangent=0.02)
edb.materials.add_dielectric_material(name='low_epoxy', 
                                      permittivity=3.8, 
                                      dielectric_loss_tangent=0.015)

edb.stackup.add_layer(layer_name='top',
                      method="add_on_bottom",
                      layer_type='signal',
                      material='copper',
                      thickness='35um')

edb.stackup.add_layer(layer_name='up_dielectric', 
                      method="add_on_bottom",
                      layer_type='dielectric',
                      material='up_epoxy',
                      thickness='100um')

layer= edb.stackup.add_layer(layer_name='signal', 
                             method="add_on_bottom",
                             layer_type='signal',
                             material='copper',
                             fillMaterial='FR4_epoxy',
                             thickness='35um',
                             etch_factor=1,
                             enable_roughness=True)
nodule_radius = '2um'
surface_ratio = 0.2

layer.top_hallhuray_nodule_radius = nodule_radius
layer.top_hallhuray_surface_ratio = surface_ratio
layer.bottom_hallhuray_nodule_radius = nodule_radius
layer.bottom_hallhuray_surface_ratio = surface_ratio
layer.side_hallhuray_nodule_radius = nodule_radius
layer.side_hallhuray_surface_ratio = surface_ratio

edb.stackup.add_layer(layer_name='low_dielectric', 
                      method="add_on_bottom",
                      layer_type='dielectric',
                      material='low_epoxy',)

edb.stackup.add_layer(layer_name='bottom',
                      method="add_on_bottom",
                      layer_type='signal', 
                      material='copper',
                      thickness='35um')

spacing_mil = 40 
width_mil = 30
line_p = edb.modeler.create_trace([('0mil', f'{(spacing_mil+width_mil)/2}mil'), ('1000mil', f'{(spacing_mil+width_mil)/2}mil')], 
                                  width=f'{width_mil}mil',
                                  layer_name='signal',
                                  start_cap_style='Flat',
                                  end_cap_style='Flat')
line_n = edb.modeler.create_trace([('0mil', f'{-(spacing_mil+width_mil)/2}mil'), ('1000mil', f'{-(spacing_mil+width_mil)/2}mil')],
                                  width=f'{width_mil}mil',
                                  layer_name='signal',
                                  start_cap_style='Flat',
                                  end_cap_style='Flat')

plane_top = edb.modeler.create_rectangle(layer_name='top', 
                                         net_name='GND',
                                         lower_left_point=('0mil', '-100mil'),
                                         upper_right_point=('1000mil', '100mil'))


plane_bot = edb.modeler.create_rectangle(layer_name='bottom', 
                                         net_name='GND',
                                         lower_left_point=('0mil', '-100mil'),
                                         upper_right_point=('1000mil', '100mil'))

edb.hfss.create_differential_wave_port(line_p, line_p.center_line[0], line_n, line_n.center_line[0])
edb.hfss.create_differential_wave_port(line_p, line_p.center_line[-1], line_n, line_n.center_line[-1])

setup = edb.create_hfss_setup()
setup.set_solution_single_frequency(frequency='5GHz', 
                                    max_num_passes=20, 
                                    max_delta_s=0.01)

edb.save_edb_as('d:/demo/test.aedb') 
edb.close_edb()
```


---

## 6. `simulation.py` behavior

- Opens `.aedb` using PyAEDT.
- Runs HFSS simulation.
- Extracts Sdiff(1, 1) and Sdiff(2, 1) (dB).
- Sdiff(2, 1) (dB) is the differential insertion loss (S21).
- Computes Zdiff from Sdiff(1,1). Zdiff = 100 * (1 + S11)/(1 - S11).
- Compares Zdiff and S21 against targets.
- Returns results to `characterization_process.py` via stdout or temp JSON.

Example PyAEDT code snippet for `simulation.py`:
```python
from pyaedt import Hfss3dLayout 

hfss = Hfss3dLayout('d:/demo/test.aedb', version='2025.2', remove_lock=True)


hfss.set_differential_pair('port1:T1', 'port1:T2', 'comm1', 'diff1')
hfss.set_differential_pair('port2:T1', 'port2:T2', 'comm2', 'diff2')

hfss.analyze(cores=4)
data = hfss.post.get_solution_data('dB(S(diff1,diff1))', context="Differential Pairs")
dbs11 = data.data_real()[0]


data = hfss.post.get_solution_data('dB(S(diff2,diff1))', context="Differential Pairs")
dbs21 = data.data_real()[0]

```

---

## 7. Special rules from the JSON

- Some layers have `loss_target: 0` (for example `in2`, `in3`); still evaluate S21 with a 0 dB target.
- Layers with empty width/spacing (for example `in2`, `in3`) are skipped for characterization.
- Etch factor may be negative (for example `-2.5`); adjustments must handle both signs proportionally.
- Variation percentages apply to absolute value: for `etchfactor = -2.5` and 20% variation, allowed range is `-2.5 ± 0.5`.
