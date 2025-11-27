# Stackup Characterization Tool 
## 1. Purpose

The tool automates stackup characterization using modeling.py for stackup/geometry creation, simulation.py for HFSS simulation, and SciPy for iterative optimization. It read a .json and adjusts parameters, generates `.aedb` projects, runs simulations, extracts Sdd11 and Sdd21, and produces characterized JSON outputs.


## 2. JSON Specification (based on uploaded file)
input: stackup_layers_1007.json
### Overview
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
the `rows` array defines each layer in the stackup. the order corresponds to physical stacking (top to bottom). it will be copied to os_stackup.json, with updated parameters after characterization.

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

---


### `characterization_process.py` (core logic)

**Pre-run:** Create a timestamped folder next to the JSON to hold `.aedb` and outputs, for example:

`stackup_characterization_YYYYMMDD_HHMMSS/`

**Workflow per signal layer:**

1. Identify signal layers (`type == "conductor"` and both `width` and `spacing` set).
2. Extract initial parameters: width, spacing, etchfactor, thickness, hallhuray_surface_ratio, nodule_radius; dielectric thickness/dk/df above and below.
3. Prepare modeling parameters using the dielectric layers immediately above and below (physical ordering).
4. Create `.aedb` via `modeling.py` (subprocess) with layer geometry, dielectric stack, reference layers, frequency, and variables.
5. Run HFSS via `simulation.py` (subprocess); extract Zdiff and dB(S21).
6. Evaluate against targets (`target ± tolerance`); if out of range, adjust parameters and iterate.

### 4.4 Parameter adjustment priority

Adjustment priority with scipy optimization (minimize difference from targets):

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

Update the original JSON with characterized parameters for each signal layer and save as `characterized_stackup.json` in the output folder. 



