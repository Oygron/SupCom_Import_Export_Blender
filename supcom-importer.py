#**************************************************************************************************
# Supreme Commander Importer for Blender3D - www.blender3d.org
#
# Written by dan - www.sup-com.net
#
# History
#   0.1.0   06/06/06   - Initial version.
#   0.2.0   06/06/10   - Added SCA (Animation) support
#   0.3.0   06/07/02   - Alpha release
#   0.4.0   2014-07-13 - Adapted to Blender 2.71
#
# Todo
#   - Material/uv map 2
#   - Bone pos/rot for scm & sca. Not perfect to use gentle words.
#   - Make sca loading independent of the scm_mesh. (e.g get bone pos/loc from armature instead)
#   - GUI for loading
#   - Progress bars
#
#**************************************************************************************************

bl_info = {
    "name": "Supcom Importer",
    "author": "dan & Brent & Oygron",
    "version": (0,4,0),
    "blender": (2, 71, 0),
    "location": "File -> Import",
    "description": "Imports Supcom files",
    "warning": "",
    "wiki_url": "http://forums.gaspowered.com/"
                "viewtopic.php?t=17286",
    "category": "Import-Export",
}

DEBUGLOG = False

import bpy
#import Blender

#from Blender import NMesh, Scene, Object

from mathutils import *

from bgl import *


import os
from os import path


import struct
import string
import math
from math import *
from bpy_extras.io_utils import unpack_list, unpack_face_list

from string import *
from struct import *

from bpy.props import *

from time import sleep

VERSION = '4.0'

sca_filepath = [ "", "", "None"]
scm_filepath = [ "", "", "None"]
######################################################
# User defined behaviour, Select as you need
######################################################

#Enable Progress Bar ( 0 = faster )
PROG_BAR_ENABLE = 0
#how many steps a progress bar has (the lesser the faster)
PROG_BAR_STEP = 25

#LOG File for debuging
#Enable LOG File (0 = Disabled , 1 = Enabled )
LOG_ENABLE = 0
#Filename / Path. Default is blender directory Filename SC-E_LOG.txt
LOG_FILENAME = "SC-E_LOG.txt"



######################################################
# Init Supreme Commander SCM( _bone, _vertex, _mesh), SCA(_bone, _frame, _anim) Layout
######################################################
xy_to_xz_transform = Matrix(([1, 0, 0], [ 0, 0, 1], [ 0, -1, 0])).to_4x4()
	#	-1	0	0
	#	0	0	1
	#	0	1	0

#export matrix
xz_to_xy_transform = Matrix(([ 1, 0, 0],
							[ 0, 0, -1],
							[ 0, 1, 0])).to_4x4()

globMesh = []
MArmatureWorld = Matrix()

def my_popup(msg):
	def draw(self, context):
		self.layout.label(msg)
	bpy.context.window_manager.popup_menu(draw, title="Error", icon='ERROR')

def my_popup_warn(msg):
	def draw(self, context):
		self.layout.label(msg)
	bpy.context.window_manager.popup_menu(draw, title="Warning", icon='ERROR')



optionsList = [
        ("1","stuff 1","0"),("2","stuff 2","0"),("3","stuff 3","0")]

counter = 0



def uvtex_items(self, context):
	return optionsList
#    return [(t.name, t.name, t.name) for t in context.object.data.uv_textures]

class SimpleOperator(bpy.types.Operator):
	"""Tooltip"""
	bl_idname = "object.simple_operator"
	bl_label = "Simple Object Operator"
	#bl_options = {'REGISTER', 'UNDO'}
	
	optsList = bpy.props.EnumProperty(items=[])
	
	meshBones = None
	anim = None
	objBoneNames = None
	bone_num = None
	
	
	@classmethod
	def poll(cls, context):
		print("poll")
		return True
	
	def invoke(self, context, event):
		print("invoke")
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		print("draw")
		layout = self.layout
		col = layout.column()
		col.prop(self, "optsList", expand=True)
	
	def execute(self, context):
		print("execute")
		print("choice",self.optsList)
		
		self.anim.bonenames[self.bone_num] = self.optsList
		
		check_bone(self.meshBones,self.anim,self.objBoneNames,self.bone_num + 1)
		
		return {'FINISHED'}



class scm_bone :

	name = ""
	#rest_pose_inv = []
	rel_mat = Matrix()
	rel_mat_inv = Matrix()
	position = []
	rotation = []
	#abs_pos = []
	parent = 0
	parent_index = 0

	rel_matrix_inv = []
	#children = []
	#numchildren = 0
	#global xy_to_xz_transform

	def __init__(self, name, rest_pose_inv = None, rotation = None, position = None, parent_index = 0):
		self.name = name
		#self.rest_pose_inv = [[0.0] * 4] * 4
		#self.position = [0.0] * 3
		#self.rotation = [0.0] * 4
		
		self.parent_index = parent_index
		
		if rest_pose_inv == None:
			self.rel_mat_inv = Matrix(([0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]))
			self.rel_mat = Matrix(([0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]))
		else:
			self.rel_mat_inv = rest_pose_inv
			self.rel_mat = rest_pose_inv.inverted()
		
		if rotation == None:
			self.rotation = Quaternion((0,0,0,0))
		else:
			self.rotation = rotation
		
		if position == None:
			self.position = Vector((0,0,0))
		else:
			self.position = position



	def load(self, file):
		#global xy_to_xz_transform
		bonestruct = '16f3f4f4i'
		buffer = file.read(struct.calcsize(bonestruct))
		readout = struct.unpack(bonestruct, buffer)

		#supcom information:
		readRPI = Matrix(([0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]))
		#// Inverse transform of the bone relative to the local origin of the mesh
		#// 4x4 Matrix with row major (i.e. D3D default ordering)
		for i in range(4):
			readRPI[i] = readout[i*4:i*4+4]

		self.rel_mat_inv = Matrix((readRPI[0], readRPI[1], readRPI[2], readRPI[3]))#*xy_to_xz_transform #note rot here changes pointing direction of spikie
		
		
		self.rel_mat = self.rel_mat_inv.inverted()


		#// Position relative to the parent bone.
		pos = readout[16:19]
		self.position = Vector((pos[0], pos[1], pos[2]))

		#// Rotation relative to the parent bone.
		rot = readout[19:23]
		self.rotation = Quaternion(( rot[0], rot[1], rot[2], rot[3] ))

		#// Index of the bone's parent in the SCM_BoneData array
		self.parent_index = readout[24]
		
		# Read bone name
		#oldpos = file.tell()
		#file.seek(bone[..], 0)
		#self.name = file.readline()
		#file.seek(oldpos, 0)

		self.dump()
		return self
		


	def dump(self):
		print( 'Bone       ', self.name)
		print( 'Position   ', self.position)
		print( 'Rotation   ', self.rotation)
		print( 'Parent Idx ', self.parent_index)
		if (self.parent != 0):
			print( 'Parent     ', self.parent.name)
		else:
			print( 'Parent     <NONE>')
		print( 'Rest Pose Inv.',self.rel_mat_inv)
		print( 'Rest Pose',self.rel_mat)
		#for row in range(4):
			#print( '  ', self.rest_pose_inv[row])

class scm_vertex :

	position = []
	tangent = []
	normal = []
	binormal = []
	uv1 = []
	uv2 = []
	bone_index = []

	def __init__(self):
		self.position 	= Vector((0,0,0))
		self.tangent 	= Vector((0,0,0))
		self.normal 	= Vector((0,0,0))
		self.binormal 	= Vector((0,0,0))
		self.uv1 	= Vector((0,0))
		self.uv2 	= Vector((0,0))
		self.bone_index = [0]*4

	def load(self, file):

		vertstruct = '3f3f3f3f2f2f4B'
		vertsize = struct.calcsize(vertstruct)

		buffer = file.read(vertsize)
		vertex = struct.unpack(vertstruct, buffer)

		self.position = vertex[0:3]
		self.tangent = vertex[3:6]
		self.normal = vertex[6:9]
		self.binormal = vertex[9:12]
		self.uv1 = vertex[12:14]
		self.uv2 = vertex[14:16]
		self.bone_index = vertex[16:20]

		return self

	def dump(self):
		print( 'position ', self.position)
		print( 'tangent  ', self.tangent)
		print( 'normal   ', self.normal)
		print( 'binormal ', self.binormal)
		print( 'uv1      ', self.uv1)
		print( 'uv2      ', self.uv2)
		print( 'bones    ', self.bone_index)


class scm_mesh :

	bones = []
	vertices = []
	faces = []
	info = []
	filename = ""

	def __init__(self):
		self.bones = []
		self.vertices = []
		self.faces = []
		self.info = []
		self.filename = ""

	def load(self, filename):
		global xy_to_xz_transform
		self.filename = filename
		scm = open(filename, 'rb')

		# Read header
		#headerstruct = '4s11L'
		headerstruct = '4s11I'
		buffer = scm.read(struct.calcsize(headerstruct))
		header = struct.unpack(headerstruct, buffer)

		#print("buffer",buffer)
		for h in header:
			print(h)

		marker = header[0].decode('ascii')
		version = header[1]
		boneoffset = header[2]
		bonecount = header[3]
		vertoffset = header[4]
		extravertoffset = header[5]
		vertcount = header[6]
		indexoffset = header[7]
		indexcount = header[8]
		tricount = indexcount // 3 #?
		infooffset = header[9]
		infocount = header[10]
		totalbonecount = header[11]

		if (marker != 'MODL'):
			print( 'Not a valid scm')
			my_popup("Not a valid scm")
			return

		if (version != 5):
			print( 'Unsupported version (%d)' % version)
			my_popup('Unsupported version (%d)' % version)
			return

		# Read bone names
		scm.seek(pad(scm.tell()), 1)
		length = (boneoffset - 4) - scm.tell()

		# This should probably be handeled by the scm_bone reader as it contains the nameoffset. But I'm lazy
		# and logic tells me it's written in the same order as the bones.
		buffer = scm.read(length)
		rawnames = struct.unpack(str(length)+'s',buffer)

		b_bonenames = (rawnames[0].split(b'\0'))[:-1]

		bonenames = [b.decode() for b in b_bonenames]
		print("bonenames",bonenames)
		# Read bones
		scm.seek(boneoffset, 0)
		for b in range(0, totalbonecount):
			bone = scm_bone(bonenames[b])
			bone.load(scm)
			self.bones.append(bone)

		#show them (for debug)
		#for b in range(0, totalbonecount):
			#print( "bone %d has %d children = " %(b, self.bones[b].numchildren))

		# Set parent (this could probably be done in the other loop since parents are usually written to the file
		# before the children. But you never know..
		for bone in self.bones:
			if (bone.parent_index != -1):
				bone.parent = self.bones[bone.parent_index]
			else:
				bone.parent = 0

			# the bone matrix relative to the parent.
			if (bone.parent != 0):
				mrel = (bone.rel_mat) * Matrix(bone.parent.rel_mat).inverted() #* xy_to_xz_transform
				bone.rel_matrix_inv = Matrix(mrel).inverted()
			else:
				mrel = bone.rel_mat * xy_to_xz_transform  #there is no parent
				bone.rel_matrix_inv = Matrix(mrel).inverted()



		# Read vertices
		scm.seek(vertoffset, 0)
		for b in range(0, vertcount):
			vert = scm_vertex()
			vert.load(scm)
			self.vertices.append(vert)

		# Read extra vertex data
		# Not implemented in Sup Com 1.0!

		# Read indices (triangles)
		tristruct = '3h'
		trisize = struct.calcsize(tristruct)

		scm.seek(indexoffset, 0)
		for t in range(tricount):
			buffer = scm.read(trisize)
			face = struct.unpack(tristruct, buffer)
			self.faces.append(list(face)+[0])


		# Read info
		if (infocount > 0):
			scm.seek(infooffset)
			buffer = scm.read()
			rawinfo = struct.unpack(str(len(buffer))+'s',buffer)
			b_info = rawinfo[0].split(b'\0')[:-1]
			self.info = [b.decode() for b in b_info]
			print("self.info",self.info)

		scm.close()

		return self

	def dump(self):
		print( '')
		print( 'Filename: ', self.filename)
		print( 'Bones ', len(self.bones))
		print( 'Verts ', len(self.vertices))
		print( 'Faces ', len(self.faces))
		print( '')
		print( 'INFO: ')
		for info in self.info:
			print( '  ', info)



class sca_bone:

	name = ''
	position = []
	rotation = []
	#changed: rototation -> rotation
	pose_pos = []
	pose_rot = []
	rel_matrix = []
	pose_matrix = []
	#rel_mat = None

	def __init__(self, pos, rot, name_):
		self.position = pos
		self.rotation = rot
		self.name = name_
		self.rel_matrix = None
		self.pose_matrix = None
		#self.rel_mat = None


	def dump(self):
		print( 'Position ', self.position)
		print( 'Rotation ', self.rotation)



class sca_frame:

	keytime = 0.0
	keyflags = 0
	bones = []
	anim = None

	def __init__(self, anim):
		self.keytime = 0.0
		self.keyflags = 0
		self.bones = []
		self.anim = anim

	def load(self, file,bonenames):
		frameheader_fmt = 'fi'
		frameheader_size = struct.calcsize(frameheader_fmt)
		buffer = file.read(frameheader_size)

		(self.keytime, self.keyflags) = struct.unpack(frameheader_fmt, buffer)

		posrot_fmt = '3f4f'
		posrot_size = struct.calcsize(posrot_fmt)

		for b in range (0, self.anim.numbones) :
			buffer = file.read(posrot_size)
			posrot = struct.unpack(posrot_fmt, buffer)
			bone = sca_bone(posrot[0:3], posrot[3:7],bonenames[b])
			self.bones.append(bone)

	def dump(self):
		print( 'Time  ', self.keytime)
		print( 'Flags ', self.keyflags)



class sca_anim :

	filename = ""
	frames = []
	bones = []
	bonelinks = []
	bonenames = []
	numbones = 0
	duration = 0.0

	def __init__(self):
		self.filename = ""
		self.frames = []
		self.bones = []
		self.numbones = 0
		self.bonelinks = []
		self.bonenames = []
		self.duration = 0.0




	def calcAnimBoneMatrix(self, frame, bone_index, armature_bones, frame_index):
		global xy_to_xz_transform

		bone = frame.bones[bone_index];
		
		
		
		parent_index = self.bonelinks[bone_index]

		# note that the pos/rot of the armature_bones are still in relative supcom coordinates.
		# so we can correct the relative pos-increase by the relative armature-increase
		pose_rel_pos = Vector(bone.position)
		pose_rel_rot = Quaternion(bone.rotation)



		# the matrix representation... it's easier to work with matrix notation I think.
		# the rotation:

		pose_rel_matrix = pose_rel_rot.to_matrix()

		pose_rel_matrix.resize_4x4()

		pose_rel_matrix.transpose()

		#if frame_index == 0 or frame_index == 40:
		#	print ('frame',frame_index)
		#	print ('bone',bone_index)
		#	print ('parent_index',parent_index)
		#	print ('pose_rel0\n',pose_rel_matrix)

		# the translation:
		pose_rel_matrix.transpose()
		pose_rel_matrix.translation = pose_rel_pos
		pose_rel_matrix.transpose()

		#if frame_index == 0 or frame_index == 40:
		#	print ('pose_rel1\n',pose_rel_matrix)


		if (parent_index == -1) :
			# for the root bone, this is already the absolution pos/rot, but,
			# the root bone should be rotated into the blender coordinates
			bone.rel_matrix = pose_rel_matrix * xy_to_xz_transform

			#testmat =(bone.rel_mat) * Matrix(bone.parent.rel_mat).invert()

		if (parent_index >= 0):
			# for all the children, they are seen relative to the parents.
			bone.rel_matrix = pose_rel_matrix

		# the (rendered) animation positions are relative to
		# both the parent, and to the relative rest position of the bone.
		#rechercher avec le nom, ici on a juste l'index, qui diffèrent entre le fichier de mesh et l'animation OK
		restBone = None
		for rBone in armature_bones:
			#print ("name",rBone.name)
			if rBone.name == bone.name:
				restBone = rBone
				break
		
		if (restBone == None):
			my_popup(bone.name + " not found")
			print(bone.name + " not found")
			#return
		
		#bone.pose_matrix = Matrix(bone.rel_matrix * armature_bones[bone_index].rel_matrix_inv)#* xy_to_xz_transform)
		#print ("bone.rel_matrix",bone.rel_matrix)
		#print ("restBone.rel_matrix_inv",restBone.rel_matrix_inv)
		bone.pose_matrix = Matrix(bone.rel_matrix * restBone.rel_matrix_inv)#* xy_to_xz_transform)

		# pose position relative to the armature
		bone.pose_matrix.transpose()
		bone.pose_pos = Vector(bone.pose_matrix.translation)

		bone.pose_rot = bone.pose_matrix.to_quaternion()
		#if frame_index == 0 or frame_index == 40:
		#	print ('rel\n',bone.rel_matrix)
		#	print ('inv\n',armature_bones[bone_index].rel_matrix_inv)
		#	print ('mat\n',bone.pose_matrix)
		#	print ("posInit",bone.position)
		#	print ("rotInit",bone.rotation)
		#	print ("posf",bone.pose_pos)
		#	print ("rotf",bone.pose_rot)
		
		
		#frame.bones[bone_index] = bone;


	def load(self, filename):
		self.filename = filename
		sca = open(filename, 'rb')

		# Read header
		headerstruct = '4siifiiiii'
		buffer = sca.read(struct.calcsize(headerstruct))
		header = struct.unpack(headerstruct, buffer)
		print('header', header)
		(magic,             \
		 version,           \
		 numframes,         \
		 self.duration,     \
		 self.numbones,     \
		 namesoffset,       \
		 linksoffset,       \
		 animoffset,        \
		 framesize) = struct.unpack(headerstruct, buffer)

		if (magic != b'ANIM'):
			print( 'Not a valid .sca animation file')
			my_popup('Not a valid .sca animation file')
			return

		if (version != 5):
			print( 'Unsupported sca version: %d'  % version)
			my_popup( 'Unsupported sca version: %d'  % version)
			return

		# Read bone names
		sca.seek(namesoffset, 0)
		length = linksoffset - namesoffset
		buffer = sca.read(length)
		rawnames = struct.unpack(str(length)+'s',buffer)
		b_bonenames = rawnames[0].split(b'\0')[:-1]
		self.bonenames = [b.decode() for b in b_bonenames]


		# Read links
		links_fmt = str(self.numbones)+'i'
		links_size = struct.calcsize(links_fmt)

		buffer = sca.read(links_size)
		self.bonelinks = struct.unpack(links_fmt, buffer)

		posrot_fmt = '3f4f'
		posrot_size = struct.calcsize(posrot_fmt)

		sca.seek(animoffset)
		buffer = sca.read(posrot_size)
		root_posrot = struct.unpack(posrot_fmt, buffer)

		for f in range (0, numframes) :
			frame = sca_frame(self)
			frame.load(sca , self.bonenames)
			self.frames.append(frame)

		sca.close()

		return self

	def dump(self):
		print( 'SCA:  ', self.filename)
		print( 'Duration: %fs' % self.duration)
		print( 'Num loaded frames ', len(self.frames))

		print( 'Bonelinks')
		for link in self.bonelinks:
			print( ' ', link)

		print( 'Bone names')
		for name in self.bonenames:
			print( ' ', name)


def pad(size):
	val = 32 - (size % 32)

	if (val > 31):
		return 0

	return val


#**************************************************************************************************
# Blender Interface
#**************************************************************************************************

def read_scm() :
	global xy_to_xz_transform
	global scm_filepath # [0] both [1] path [2] name
	global sca_filepath # [0] both [1] path [2] name

	print( "=== LOADING Sup Com Model ===")
	print( "")

	
	#global counter
	#
	#if (counter < 10):
	#	
	#	bpy.utils.unregister_class(SimpleOperator)
	#	SimpleOperator.bl_label = "toto"+str(counter)
	#	bpy.utils.register_class(SimpleOperator)
    #
	#	bpy.ops.object.simple_operator('INVOKE_DEFAULT')
	#	
	#	return
	#


	#xy_to_xz_transform.resize_4x4()
	#bpy.ops.object.mode_set(mode='OBJECT')
	#scene = Blender.Scene.GetCurrent()
	scene = bpy.context.scene
	mesh = scm_mesh()

	if (mesh.load(scm_filepath[0]) == None):
		print( 'Failed to load %s' %scm_filepath[2])
		my_popup( 'Failed to load %s' %scm_filepath[2])
		return

	#ProgBarLSCM = ProgressBar( "Imp: load SCM", (2*len(mesh.vertices) + len(mesh.faces)))

	armature_name = scm_filepath[2].rstrip(".scm")
	print( "armature ", armature_name)

	###		CREATE ARMATURE
	armData = bpy.data.armatures.new(armature_name)
	armData.show_axes = True

	armObj = bpy.data.objects.new(armature_name, armData)

	scene.objects.link(armObj)
	scene.objects.active = armObj
	armObj.select = True
	armObj.show_x_ray = True

	bpy.ops.object.mode_set(mode='EDIT')

	for index in range(len(mesh.bones)):
		#print('boneIndex',index)
		bone = mesh.bones[index]
		#print('boneName',bone.name)

		blender_bone = armData.edit_bones.new(bone.name)
		
		#not nice parent may not exist,  but usualy should exist (depends on storing in scm)
		if (bone.parent != 0) :
			blender_bone.parent = armData.edit_bones[bone.parent.name]


		t_matrix = bone.rel_mat * xy_to_xz_transform
		loc,rot,sca = t_matrix.transposed().decompose()
		blender_bone.head = loc
		blender_bone.tail = (rot.to_matrix() * Vector((0,1,0))) + blender_bone.head
		blender_bone.matrix = t_matrix.transposed()


	bpy.ops.object.mode_set(mode='OBJECT')
	
	
	meshData = bpy.data.meshes.new('Mesh')


	#add verts
	vertlist = []
	for vert in mesh.vertices:
		#ProgBarLSCM.do()
		vertlist.append(Vector(vert.position)*xy_to_xz_transform)


	meshData.vertices.add(len(vertlist))
	meshData.tessfaces.add(len(mesh.faces))
	meshData.vertices.foreach_set("co", unpack_list(vertlist))
	meshData.tessfaces.foreach_set("vertices_raw", unpack_list( mesh.faces))


	print(len(meshData.tessfaces))


	meshData.uv_textures.new(name='UVMap')


	for uv in meshData.tessface_uv_textures: # uv texture
		print(uv)
		for face in meshData.tessfaces:# face, uv
			uv1 = mesh.vertices[mesh.faces[face.index][0]].uv1
			uv.data[face.index].uv1 = Vector((uv1[0], 1.0-uv1[1]))
			uv1 = mesh.vertices[mesh.faces[face.index][1]].uv1
			uv.data[face.index].uv2 = Vector((uv1[0], 1.0-uv1[1]))
			uv1 = mesh.vertices[mesh.faces[face.index][2]].uv1
			uv.data[face.index].uv3 = Vector((uv1[0], 1.0-uv1[1]))

	mesh_obj = bpy.data.objects.new('Mesh', meshData)
	scene.objects.link(mesh_obj)
	scene.objects.active = mesh_obj
	mesh_obj.select = True

	meshData.update()

	#assigns vertex groups #mesh must be in object
	for bone in mesh.bones:
		mesh_obj.vertex_groups.new(bone.name)


	for vgroup in mesh_obj.vertex_groups:
		#print(vgroup.name, ":", vgroup.index)
		for vertex_index in range(len(mesh.vertices)):
			#bone index
			vertex = mesh.vertices[vertex_index]
			bone_index = vertex.bone_index[0]
			boneName = mesh.bones[bone_index].name
			if boneName == vgroup.name:
				vgroup.add([vertex_index], 1.0, 'ADD')

	meshData.update()

	bpy.context.scene.update()


	bpy.ops.object.select_all(action='DESELECT')

	mesh_obj.select = False
	armObj.select = False

	#armObj.select = True
	mesh_obj.select = True
	armObj.select = True
	scene.objects.active = armObj
	bpy.ops.object.parent_set(type="ARMATURE")

	if len(mesh.info):
		print( "=== INFO ===")
		for info in mesh.info:
			print( "",info)

	print( "=== COMPLETE ===")

	global globMesh
	globMesh = mesh
	

def iterate_bones(meshBones, bone, parent = None, scm_parent_index = -1):

	global MArmatureWorld
	global xz_to_xy_transform




	if (parent != None and bone.parent.name != parent.name):
		my_popup("Error: Invalid parenting in bone ... multiple parents?!")
		print("Error: Invalid parenting in bone ... multiple parents?!")
		#print( "Invalid parenting in bone", bone.name," and parent ", parent.name)
		return

	b_rest_pose 	= Matrix(([0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]))
	b_rest_pose_inv = Matrix(([0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]))
	b_rotation		= Quaternion(( 0,0,0,0 ))
	b_position		= Vector(( 0,0,0 ))
	b_index = len(meshBones)


	#print ("iterate bone",bone.name)
	bone_matrix = bone.matrix_local.transposed()
	#print ("bone_matrix",bone_matrix)
	
	# Calculate the inverse rest pose for the bone #instead bonearmmat*worldmat = Matrix['BONESPACE']
	b_rest_pose 	= bone_matrix * MArmatureWorld
	b_rest_pose_inv = ( b_rest_pose * xz_to_xy_transform ).inverted()

	if (parent == None):
		rel_mat = b_rest_pose * xz_to_xy_transform
		#root pos is the same as the rest-pose
	else:
		parent_matrix_inv = Matrix( parent.matrix_local.transposed() ).inverted()
		rel_mat = Matrix(bone_matrix * parent_matrix_inv)
		# must be BM * PMI in that order
		# do not use an extra (absolute) extra rotation here, cause this is only relative
	
	#print ("rel_mat",rel_mat)
	
	#  Position & Rotation   relative to parent (if there is a parent)
	b_rotation = rel_mat.transposed().to_quaternion()#.normalize()
	
	#print ("b_rotation",b_rotation)
	
	#row 3, cols 0,1,2 indicate position
	b_position = rel_mat.transposed().to_translation()
	
	#print ("b_position",b_position)
	
	#def __init__(self, name, rest_pose_inv, rotation, position, parent_index):
	#print ("boneReadName",bone.name)
	#print ("b_rest_pose_inv",b_rest_pose_inv)
	sc_bone = scm_bone( bone.name, b_rest_pose_inv, b_rotation, b_position, scm_parent_index )

	meshBones.append(sc_bone)

	# recursive call for all children
	if (bone.children != None):
		for child in bone.children:
			iterate_bones( meshBones, child, bone, b_index )

def get_mesh_bones():
	scene = bpy.context.scene

	# Get Selected object(s)
	selected_objects = bpy.context.selected_objects

	# Priority to selected armature
	arm_obj = None
	for obj in selected_objects:
		if obj.type == "ARMATURE":
			arm_obj = obj
			break

	# Is there one armature? Take this one
	if arm_obj == None :
		for obj in scene.objects:
			if obj.type == "ARMATURE":
				arm_obj = obj
				break

	if arm_obj == None:
		popup("Error: Please select your armature.%t|OK")
		return
		
	MArmatureWorld = Matrix(arm_obj.matrix_world)
	
	arm = arm_obj.data
	meshBones = []
	for bone in arm.bones.values():
		if (bone.parent == None):
			iterate_bones(meshBones, bone)
	
	if meshBones == []:
		print ('No bone in project')
		my_popup('No bone in project')
		return
		
	for bone in meshBones:
		if (bone.parent_index != -1):
			bone.parent = meshBones[bone.parent_index]
		else:
			bone.parent = 0

		# the bone matrix relative to the parent.
		if (bone.parent != 0):
			mrel = (bone.rel_mat) * Matrix(bone.parent.rel_mat).inverted() #* xy_to_xz_transform
			bone.rel_matrix_inv = Matrix(mrel).inverted()
		else:
			mrel = bone.rel_mat * xy_to_xz_transform  #there is no parent
			bone.rel_matrix_inv = Matrix(mrel).inverted()
				
	#debug
	#for b in meshBones:
	#	print ("name",b.name)
	#	print ("inv",b.rel_matrix_inv)
	#	print ("inv0",b.rel_mat_inv)
	
	return meshBones

def read_anim(mesh):
	
	#TODO: faire en sorte que mesh soit importé de l'objet courant
	
	#if mesh == []:
	#	print ('meshUndefined')
	#	my_popup('Mesh Undefined')
	#	return
		
	#meshBones = mesh.bones
	
	#for b in mesh.bones:
	#	print ("name",b.name)
	#	print ("inv",b.rel_matrix_inv)
	#	print ("inv0",b.rel_mat_inv)
		
	global xy_to_xz_transform
	global sca_filepath # [0] both [1] path [2] name
	global MArmatureWorld
	#xy_to_xz_quat = xy_to_xz_transform.toQuat()

	print( "=== LOADING Sup Com Animation ===")
	print( "")

	anim = sca_anim()
	anim.load(sca_filepath[0])
	
	meshBones = get_mesh_bones()
	
	objBoneNames = [rBone.name for rBone in meshBones]
	#print (objBoneNames)
	return check_bone(meshBones,anim,objBoneNames,0)
	
	
def check_bone(meshBones,anim,objBoneNames,bone_num):
	if (bone_num < len(anim.bonenames)):
		#print("check_bone",anim.bonenames[bone_num])
		if anim.bonenames[bone_num] not in objBoneNames:
			print (anim.bonenames[bone_num],"not found")
			bpy.utils.unregister_class(SimpleOperator)
			
			SimpleOperator.bl_label = anim.bonenames[bone_num]+" not found, select substitute"
			
			SimpleOperator.meshBones = meshBones
			SimpleOperator.anim = anim
			SimpleOperator.objBoneNames = objBoneNames
			SimpleOperator.bone_num = bone_num
			
			itemList = [(b,b,b) for b in objBoneNames]
			itemList += [("_importer_Discard_","Discard","Discard")]
			SimpleOperator.optsList = bpy.props.EnumProperty(items=itemList)
				
			bpy.utils.register_class(SimpleOperator)
			
			bpy.ops.object.simple_operator('INVOKE_DEFAULT')
			
			return
		else:
			return check_bone(meshBones,anim,objBoneNames,bone_num+1)
	else:
		return read_end_anim(meshBones,anim)

def read_end_anim(meshBones,anim):
	global xy_to_xz_transform
	global sca_filepath # [0] both [1] path [2] name
	#ProgBarLSCA = ProgressBar( "Imp: Frames", len(anim.frames))
	
	#print ("post traitement",anim.bonenames)
	
	#scene = Blender.Scene.GetCurrent()
	scene = bpy.context.scene
	context = bpy.context

	arm_obj = None
	for obj in scene.objects:
		if obj.type == "ARMATURE":
			arm_obj = obj
			break

	if arm_obj == None:
		print( "couldn't apply animation, no armature in the scene" )
		my_popup("couldn't apply animation, no armature in the scene")
		return
	#arm_obj = armObj

	print( arm_obj.name)
	arm_obj.animation_data_clear()
	arm_obj.animation_data_create()
	action = bpy.data.actions.new(name=sca_filepath[2].rstrip(".sca"))
	arm_obj.animation_data.action = action

	pose = arm_obj.pose

	for frame_index in range(len(anim.frames)):
		#if (frame_index == 0):
		#	print ("frame",frame_index)
		#print ("frame",frame_index)
		#ProgBarLSCA.do()

		context.scene.frame_set(frame_index + 1)
		frame = anim.frames[frame_index]

		# this inserts the bones information into blender.
		for b in range(len(frame.bones)):
			if (anim.bonenames[b] != "_importer_Discard_"):
				if (frame_index == 0):
					print("bone",anim.bonenames[b])
				
				pose_bone = pose.bones[anim.bonenames[b]]

				# this changes the relative orientation (supcom) to absolute orientation (blender)
				frame.bones[b].name = anim.bonenames[b]
				anim.calcAnimBoneMatrix(frame, b, meshBones, frame_index)

				if (pose_bone == None):
					print( 'Frame %d - Bone \"%s\" not found' % (frame_index, anim.bonenames[b]))
					my_popup_warn( 'Frame %d - Bone \"%s\" not found' % (frame_index, anim.bonenames[b]))
					continue

				anim_bone = frame.bones[b]
				#if (frame_index == 0):
				#	print("matrix",anim_bone.pose_matrix)
				#	print("posFin",anim_bone.pose_pos)
				#	print("rotFin",anim_bone.pose_rot)

				pose_bone.location = anim_bone.pose_pos
				pose_bone.rotation_quaternion = anim_bone.pose_rot
				pose_bone.scale = Vector((1,1,1))

				pose_bone.keyframe_insert("location")
				pose_bone.keyframe_insert("rotation_quaternion")
				pose_bone.keyframe_insert("scale")

	#Blender.Set("curframe", 1)
	context.scene.frame_set(1)

	#scene = Blender.Scene.GetCurrent()
	#context = scene.getRenderingContext()

	context.scene.frame_end = len(anim.frames)
	bpy.context.scene.update()

	print( "=== COMPLETE ===")

class IMPORT_OT_scm(bpy.types.Operator):
	'''Load a skeleton mesh psk File'''
	global scm_filepath
	bl_idname = "import_scene.scm"
	bl_label = "Import SCM"
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	bl_options = {'UNDO'}

	# List of operator properties, the attributes will be assigned
	# to the class instance from the operator settings before calling.
	filepath = StringProperty(
			subtype='FILE_PATH',
			)
	filter_glob = StringProperty(
			default="*.scm",
			options={'HIDDEN'},
			)

	def execute(self, context):
		#getInputFilenamescm(self, self.filepath, self.importmesh, self.importbone, self.bDebugLogSCM,
		#                    self.importmultiuvtextures)
		scm_filepath[0] = self.filepath
		length = len(self.filepath)
		if self.filepath[length-4:length] == ".scm" :
			scm_filepath[1], scm_filepath[2]  = os.path.split(self.filepath)
			#self._timer = context.window_manager.event_timer_add(0.01, context.window)
			#print("timer launched")
			#context.window_manager.modal_handler_add(self)
			read_scm()
			#sleep(10)
			#return {'RUNNING_MODAL'}
			return {'FINISHED'}
			
		else:
			scm_filepath[0] = ""
			scm_filepath[1] = ""
			scm_filepath[2] = "Non Supported"
			return {'FINISHED'}

	def invoke(self, context, event):
		wm = context.window_manager
		wm.fileselect_add(self)
		return {'RUNNING_MODAL'}

class IMPORT_OT_sca(bpy.types.Operator):
	'''Load a skeleton anim sca File'''
	bl_idname = "import_anim.sca"
	bl_label = "Import SCA"
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"

	filepath = StringProperty(
			subtype='FILE_PATH',
			)
	filter_glob = StringProperty(
			default="*.sca",
			options={'HIDDEN'},
			)

	def execute(self, context):
		#getInputFilenamesca(self,self.filepath,context)
		sca_filepath[0] = self.filepath
		length = len(self.filepath)
		if self.filepath[length-4:length] == ".sca" :
			sca_filepath[1], sca_filepath[2]  = os.path.split(self.filepath)
			global globMesh
			read_anim(globMesh)
		else:
			sca_filepath[0] = ""
			sca_filepath[1] = ""
			sca_filepath[2] = "Non Supported"
		return {'FINISHED'}

	def invoke(self, context, event):
		wm = context.window_manager
		wm.fileselect_add(self)
		return {'RUNNING_MODAL'}


def menu_func(self, context):
	self.layout.operator(IMPORT_OT_scm.bl_idname, text="Supcom Mesh (.scm)")
	self.layout.operator(IMPORT_OT_sca.bl_idname, text="Supcom Anim (.sca)")

def register():
	bpy.utils.register_module(__name__)
	bpy.types.INFO_MT_file_import.append(menu_func)

def unregister():
	bpy.utils.unregister_module(__name__)
	bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
	register()
