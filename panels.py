# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
# from bpy.app.handlers import persistent

# from .operators import (
#     SWV_OT_SaveIncrement,
#     SWV_OT_SavePublish
# )


# def update_panel(self, context):
#     # Check if we're already updating to prevent recursion
#     if getattr(update_panel, "is_updating", False):
#         return
#
#     update_panel.is_updating = True
#
#     try:
#         # Unregister the panel
#         try:
#             bpy.utils.unregister_class(SWV_PT_SaveWithVersioningPanel)
#         except:
#             pass
#
#         # Update the bl_category
#         prefs = context.preferences.addons[__package__].preferences
#         SWV_PT_SaveWithVersioningPanel.bl_category = prefs.panel_category
#
#         # Re-register the panel
#         bpy.utils.register_class(SWV_PT_SaveWithVersioningPanel)
#
#         # Save the preference
#         context.preferences.addons[__package__].preferences.panel_category = prefs.panel_category
#     finally:
#         update_panel.is_updating = False


# class SWV_UL_FileList(bpy.types.UIList):
#     def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
#         if self.layout_type in {'DEFAULT', 'COMPACT'}:
#             row = layout.row(align=True)
#             text = " | " * (item.indent - 1) + item.name
#             row.label(text=text, icon='FILE_BLEND')
#
#             # Add publish icon if the file is published
#             if item.is_published:
#                 row.label(text="", icon='ANTIALIASED')
#
#             # Add a small button to open the file
#             op = row.operator("swv.open_selected_file", text="",
#                               icon='FILEBROWSER', emboss=True)
#             op.filepath = item.name
#
#     def filter_items(self, context, data, propname):
#         items = getattr(data, propname)
#         helper_funcs = bpy.types.UI_UL_list
#
#         # Default sort
#         sorted_indices = helper_funcs.sort_items_by_name(items, "name")
#
#         # Filter
#         filtered_indices = helper_funcs.filter_items_by_name(
#             self.filter_name, self.bitflag_filter_item, items, "name",
#             reverse=self.use_filter_sort_reverse)
#
#         return filtered_indices, sorted_indices


# class SWV_PG_FileItem(bpy.types.PropertyGroup):
#     name: bpy.props.StringProperty()
#     indent: bpy.props.IntProperty()
#     is_published: bpy.props.BoolProperty()


class GPU_PT_GPUOverlayPanel(bpy.types.Panel):

    bl_label = "GPU Overlay"
    # bl_idname = "GPU_Overlay"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GPU Overlay'
    # bl_category = 'Tool'  # Default category
    # bl_order = 0  # This will be set dynamically

    # @classmethod
    # def poll(cls, context):
    #     tool_order = 100000
    #     item_order = 100000
    #     prefs = context.preferences.addons[__package__].preferences
    #     if hasattr(prefs, "panel_category"):
    #         cls.bl_category = prefs.panel_category
    #         # Set bl_order based on the category
    #         if cls.bl_category == 'Tool':
    #             # High number for Tool category (to be at the end)
    #             cls.bl_order = tool_order
    #         else:
    #             # Low number for Item category (to be at the end)
    #             cls.bl_order = -item_order
    #     else:
    #         cls.bl_category = "Tool"
    #         cls.bl_order = tool_order
    #     return True

    def draw(self, context):
        layout = self.layout
        # scene = context.scene

        # Add save buttons
        layout.label(text="GPU test")
        # row.operator("swv.save_increment", text="Increment", icon="PLUS")
        # row.operator("swv.save_publish", text="Publish", icon="ANTIALIASED")
        #
        # # Add refresh button
        # row = layout.row()
        #
        # # Open current directory button
        # row.operator("swv.open_current_dir",
        #              text="Open Current Directory", icon="FILE_FOLDER")
        #
        # row.operator("swv.refresh_file_list", text="", icon="FILE_REFRESH")
        #
        # # Add file list
        # row = layout.row()
        # row.template_list("SWV_UL_FileList", "", scene,
        #                   "file_list", scene, "file_list_index", rows=10)


classes = (
    # SWV_UL_FileList,
    # SWV_PG_FileItem,
    GPU_PT_GPUOverlayPanel,
    # SWV_PT_VersioningAddonPreferences,
)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)
