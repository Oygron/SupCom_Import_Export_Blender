SupCom_Import_Export_Blender
============================

Python scripts to import and export Supreme Commander units (.scm) and animations (.sca) in Blender.


Place the .py scripts in BlenderInstallDir/v.num/scripts/addons

They'll appear in import/export category in Blender.

Tips :
------
- To import animations (.sca), you have to have already loaded a model on Blender, either the corresponding mesh (.scm), or a custom mesh of your own, with the bones corresponding in names with the animation bones (each bone named in the animation must have a corresponding one with the same name in the mesh).

- When creating a new unit, the central bone (parent of all other bones of the armature) of the unit MUST have the same name as the unit

- There must exists only one armature in the model. 

- All vertices must be in a "Vertex Group", and each vertex group must have the name of a bone. If some vertices are not moving, just give assign them to the group with the central bone as bonename.

- An animation must be associated with an action (see the NLA editor).

- When exporting, the script will assume the unit name (and so the .scm filename) from the central bone, and the filename for the animation from the action name in Blender (can be seen in the NLA editor). So you'll have only to select the output folder, filenames will be deduced (I hope to change that later, making only a name default value that the user can change).

- All faces must be triangles. No quad or other polygon.



Tested on Blender 2.71 and Supreme Commander - Forged Alliance

known bugs :
Order of bones are not respected at export.


More informations at :
http://forums.gaspowered.com/viewtopic.php?t=17286

Credits to dan & Brent for the original version and all the engineering work. My principal job was to port the addons from blender 2.49 to blender 2.71
