# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy

import sgtk
from sgtk.platform.qt import QtGui

__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """

        print(
            operation,
            file_path,
            context,
            parent_action,
            file_version,
            read_only,
            **kwargs
        )
        if operation == "current_path":
            return bpy.data.filepath

        elif operation == "open":
            bpy.ops.wm.open_mainfile(filepath=file_path)

        elif operation == "save":
            bpy.ops.wm.save_mainfile("EXEC_AREA")

        elif operation == "save_as":
            bpy.ops.wm.save_mainfile(filepath=file_path)

        elif operation == "reset":
            if bpy.data.is_dirty:
                # changes have been made to the scene
                res = QtGui.QMessageBox.question(
                    None,
                    "Save your scene?",
                    "Your scene has unsaved changes. Save before proceeding?",
                    QtGui.QMessageBox.Yes
                    | QtGui.QMessageBox.No
                    | QtGui.QMessageBox.Cancel,
                )

                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.Yes:
                    scene_name = bpy.data.filepath
                    if not scene_name:
                        bpy.ops.wm.save_mainfile("INVOKE_AREA")
                    else:
                        bpy.ops.wm.save_mainfile(filepath=scene_name)

            # do new file:
            bpy.ops.wm.read_homefile()
            return True
