Stackup Characterization

### Stackup_viewer.html

The `stackup_viewer.html` file is a tool that allows users to:

- Import an ANSYS HFSS 3D Layout stackup XML file.
- Visualize the stackup data in an interactive table.
- Fill in impedance targets and loss targets for specified layers.
- Set up variable ranges for stackup values to optimize the design.
- Export the data as a JSON file for further analysis.

stackup_viewer.html is finished and can be used as a standalone HTML file in a web browser. data/stk_input_1007.xml is provided as an example stackup xml file. the processed output json file  is stakup_layers_1007.json. 

Following items are under development scripts to process the exported json file for stackup characterization in ANSYS HFSS 3D Layout with pyedb.

### Characterization_process.py
The `characterization_process.py` script processes the exported JSON file from `stackup_viewer.html`, performs stackup characterization based on the provided parameters, create transmission line models, set port excitations, and setups the solver configurations in ANSYS HFSS 3D Layout for simulation.

If the results meet the user-defined criteria, the script saves the characterized stackup data into a new JSON file for further processing.

IF the results do not meet the criteria, the script adjusts the stackup parameters based on the defined variable ranges and reruns the simulation until the criteria are satisfied or a maximum number of iterations is reached.

# requirements details
Iterate conductor layers only the layer with spacing and width defined will be considered as signal layer. create differential pair on the layer and set wave port excitation with refercence to the layers defined with key reference_layers. the reference layers may be one or two layers with / separator. if two layers are defined, the first layer is considered as the top reference layer and the second layer as the bottom reference layer.

pyedb is used to create differential pair, the reference layers and dielectric layers between the signal layer and reference layers. differential wave port is created with reference to the reference layers. Add HFSS setup at specified frequency in the json file. run the simulation and extract s-parameter results. analyze the dB(S11) and dB(S21) results to determine if the stackup meets the user-defined criteria. impedance_target and loss_target, the tolerance is also defined in the json file: impedace_target['tolerance'], loss_target['tolerance'].

if not meet the criteria, adjust the stackup within the defined variable in specified range defined in the json file. the priority: 
1. etch_factor of signal layer, 
2. thickness of signal layer, 
3. Dk, 
4. Df, 
5. hallhuray_surface_ratio of signal layer
6. nodule_radius of signal layer, 

if pass the requirement, stop the iteration and save the characterized stackup data into a new json file.

finally, the characterized stackup json is used to create the final stackup and output the stackup xml file for further use.







