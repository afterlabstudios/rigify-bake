import bpy

bl_info = {
    "name": "Rigify Bake Rig",
    "author": "Afterlab",
    "description": "Bake rigify. Based on https://github.com/felixSchl/bake-rigify",
    "blender": (2, 80, 0),
    "version": (1, 0, 0), 
    "support": "COMMUNITY",
    "category": "Rigging"
}

def selectBone(armature, boneName):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.select_all(action='DESELECT')
    edit_bone = armature.data.edit_bones[boneName]
    edit_bone.select = True
    bpy.ops.object.mode_set(mode='OBJECT')
    armature.data.bones.active = armature.data.bones[boneName]
    return armature.data.bones.active

def duplicateBone(): 
    bpy.ops.armature.duplicate()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    duplicated_bone = bpy.context.active_bone
    return duplicated_bone

def bake(context, armature, action, keep):
    bpy.ops.object.select_all(action="DESELECT")

    # Select Original Armature
    originalArmature = armature
    originalArmatureName = originalArmature.name
    currentType = ''
    context.view_layer.objects.active = originalArmature
    originalArmature.select_set(True)

    # Duplicated Armature
    bpy.ops.object.duplicate(linked=False)
    duplicatedArmature = context.active_object
    duplicatedArmatureName = duplicatedArmature.name
    duplicatedArmature.animation_data.action = action

    # Make single user
    bpy.ops.object.make_single_user(obdata=True)

    # Enter edit mode
    bpy.ops.object.mode_set(mode="EDIT")

    # Turn visible layers
    duplicatedArmature.data.layers = [True for _ in range(0, 32)]

    # Collect all edit bones
    editBones = duplicatedArmature.data.edit_bones
    defBoneNames = [b.name for b in editBones if b.name.startswith('DEF')]

    for defBoneName in defBoneNames:
        # Select the bone
        selectBone(duplicatedArmature, defBoneName)

        # Duplicate current bone
        bpy.ops.object.mode_set(mode="EDIT")
        duplicatedBone = duplicateBone()
        duplicatedBone.name = 'EXP%s' % defBoneName[3:]

        # Process all deformation bones
        duplicatedBone.parent = None

        # Track name for mode changes
        duplicatedBoneName = duplicatedBone.name

        # Set object mode to propagate edit mode changes
        bpy.ops.object.mode_set(mode='OBJECT')

        # Add constraints
        bpy.ops.object.mode_set(mode='POSE')
        duplicatedPoseBone = duplicatedArmature.pose.bones[duplicatedBoneName]

        c = duplicatedPoseBone.constraints.new(type='COPY_TRANSFORMS')
        c.target = duplicatedArmature
        c.subtarget = defBoneName

    # Select target bones for baking
    bpy.ops.object.mode_set(mode='EDIT')
    for b in editBones:
        if b.name.startswith('EXP') or b.name == 'root':
            b.select = True

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    # Performing bake operation in NLA area
    current_type = ''
    if not bpy.app.background:
        current_type = context.area.type
        context.area.type = 'NLA_EDITOR'
    bpy.ops.nla.bake(
        frame_start=duplicatedArmature.animation_data.action.frame_range[0],
        frame_end=duplicatedArmature.animation_data.action.frame_range[1],
        step=1,
        visual_keying=True,
        only_selected=False,
        clear_constraints=True,
        clear_parents=True,
        bake_types={'POSE'},
    )
    if not bpy.app.background:
        context.area.type = current_type

    # Set Name for Baked Action
    duplicatedArmature.animation_data.action.name = action.name + '.baked'

    # Delete all un-selected bones
    bpy.ops.object.mode_set(mode='EDIT')
    editBones = duplicatedArmature.data.edit_bones
    for b in editBones:
        if not b.select:
            editBones.remove(b)

    # Rename EXP-bones back to ``DEF`` so that vertex groups work
    dup_bone_names = []
    for b in editBones:
        b.use_deform = True
        b.name = 'DEF%s' % b.name[3:] if not b.name == 'root' else b.name
        b.layers = [False for _ in range(0, 32)]
        b.layers[0] = True
        dup_bone_names.append(b.name)

    # Remove left-over constraints (nla.bake() may leave residue)
    bpy.ops.object.mode_set(mode='POSE')
    for b in duplicatedArmature.pose.bones:
        [b.constraints.remove(c) for c in b.constraints]

    # Set the layers to what matters only
    duplicatedArmature.data.layers = [False for _ in range(0, 32)]
    duplicatedArmature.data.layers[0] = True

    # Add static root bone
    context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.mode_set(mode='EDIT')
    oldRoot = duplicatedArmature.data.edit_bones['root']
    oldRoot.name = 'dummy'
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.bone_primitive_add(name='root')
    oldRoot = duplicatedArmature.data.edit_bones['dummy']
    oldRoot.parent = duplicatedArmature.data.edit_bones['root']

    # Remove all animation from root and dummy
    bpy.ops.object.mode_set(mode='POSE')
    for b in ['root', 'dummy']:
        for f in range(int(duplicatedArmature.animation_data.action.frame_range[1] + 1)):
            duplicatedArmature.keyframe_delete('pose.bones["%s"].scale' % b, index=-1, frame=f)
            duplicatedArmature.keyframe_delete('pose.bones["%s"].location' % b, index=-1, frame=f)
            duplicatedArmature.keyframe_delete('pose.bones["%s"].rotation_euler' % b, index=-1, frame=f)
            duplicatedArmature.keyframe_delete('pose.bones["%s"].rotation_quaternion' % b, index=-1, frame=f)
            duplicatedArmature.keyframe_delete('pose.bones["%s"].rotation_axis_angle' % b, index=-1, frame=f)
        bpy.ops.pose.select_all(action='DESELECT')
        duplicatedArmature.pose.bones[b].bone.select = True
        bpy.ops.pose.loc_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.rot_clear()

    # Now re-parent all bones to the dummy and then it's done
    bpy.ops.object.mode_set(mode='EDIT')
    dummyEB = duplicatedArmature.data.edit_bones['dummy']
    for b in dup_bone_names:
        duplicatedArmature.data.edit_bones[b].parent = dummyEB

    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT') 

    if not keep:
        context.view_layer.objects.active = duplicatedArmature
        duplicatedArmature.select_set(True)
        bpy.ops.object.delete()
    else:
        duplicatedArmature.name = originalArmature.name + '.baked'
        
    context.view_layer.objects.active = originalArmature

    return {'FINISHED'}

class OBJECT_PT_rigify_bake(bpy.types.Panel):
    bl_label = 'Rigify Bake'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        actionLength = len(bpy.data.actions)
        isArma = context.active_object.type == 'ARMATURE'
        selected = context.active_object.name
 

        if actionLength and isArma:
            row = layout.row()
            row.label(text="Selected: " + str(selected), icon="OUTLINER_OB_ARMATURE") 

            row = layout.row()
            row.prop(context.scene.rigify_bake_properties, "actions")

            row = layout.row()
            col = row.column_flow(columns=2, align=True)
            row.operator('object.rigify_bake_selected')
            row.operator('object.rigify_bake_all')
        else:
            row = layout.row()
            row.label(text='Not an ARMATURE or no Actions to bake', icon="ERROR")


class OBJECT_OT_rigify_bake_selected(bpy.types.Operator): 
    bl_idname = "object.rigify_bake_selected"
    bl_label = "Bake Selected"
    bl_description = "Bake selected action from dropdown menu"
    bl_options = {'REGISTER', 'UNDO'}
 
    def execute(self, context):
        armature = context.active_object
        actionName = context.scene.rigify_bake_properties.actions
        action = bpy.data.actions.get(actionName) 

        # Perform bake operation
        bake(context, armature, action, keep=True) 

        self.report({'INFO'}, "Bake operation done.")
        return {'FINISHED'}


class OBJECT_OT_rigify_bake_all(bpy.types.Operator):
    bl_idname = "object.rigify_bake_all"
    bl_label = "Bake All"
    bl_description = "Bake all actions under bpy.data.actions. WARNING: Might crash your instance if you have dozens of actions"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object

        # Get action names
        actions = bpy.data.actions
        actionNames = []
        for action in actions:
            actionNames.append(action.name)
            
        # Perform bake operation
        i = 0
        for name in actionNames:
            action = bpy.data.actions.get(name)             
            keep = True
            if i > 0: keep = False
            bake(context, armature, action, keep) 
            i += 1
            
        self.report({'INFO'}, "Bake operation done.")

        return {'FINISHED'}
 


def getActions(self, context):
    items = [] 
    i=0
    for action in bpy.data.actions: 
        print(action.name)
        items.append((str(action.name), str(action.name), ""))
        i += 1
    return items 

class RigifyBakeProperties(bpy.types.PropertyGroup):  
    actions : bpy.props.EnumProperty(
        items=getActions, 
        default=None,
        name="Actions",
        update=None, get=None, set=None
    )


def register():
    bpy.utils.register_class(RigifyBakeProperties)
    bpy.types.Scene.rigify_bake_properties = bpy.props.PointerProperty(type=RigifyBakeProperties)
    bpy.utils.register_class(OBJECT_OT_rigify_bake_all)
    bpy.utils.register_class(OBJECT_OT_rigify_bake_selected)
    bpy.utils.register_class(OBJECT_PT_rigify_bake)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_rigify_bake_all)
    bpy.utils.unregister_class(OBJECT_OT_rigify_bake_selected)
    bpy.utils.unregister_class(OBJECT_PT_rigify_bake)
    bpy.utils.unregister_class(RigifyBakeProperties)


if __name__ == "__main__":
    register()
