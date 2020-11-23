# ----------------------------------------------------------------------------
# Copyright (c) 2020, Diego Garcia Huerta.
#
# Your use of this software as distributed in this GitHub repository, is
# governed by the Apache License 2.0
#
# Your use of the Shotgun Pipeline Toolkit is governed by the applicable
# license agreement between you and Autodesk / Shotgun.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


import os
import sys
import imp
import time
import ast
import inspect

import bpy
from bpy.types import Header, Menu, Panel, Operator
from bpy.app.handlers import load_factory_startup_post, persistent

import site

DIR_PATH = os.path.dirname(os.path.abspath(__file__))

ext_libs = os.environ.get("PYSIDE2_PYTHONPATH")

if ext_libs and os.path.exists(ext_libs):
    if ext_libs not in sys.path:
        print("Added path: %s" % ext_libs)
        site.addsitedir(ext_libs)

bl_info = {
    "name": "Shotgun Bridge Plugin",
    "description": "Shotgun Toolkit Engine for Blender",
    "author": "Diego Garcia Huerta",
    "license": "GPL",
    "deps": "",
    "version": (1, 0, 0),
    "blender": (2, 82, 0),
    "location": "Shotgun",
    "warning": "",
    "wiki_url": "https://github.com/diegogarciahuerta/tk-blender/releases",
    "tracker_url": "https://github.com/diegogarciahuerta/tk-blender/issues",
    "link": "https://github.com/diegogarciahuerta/tk-blender",
    "support": "COMMUNITY",
    "category": "User Interface",
}


PYSIDE2_MISSING_MESSAGE = (
    "\n"
    + "-" * 80
    + "\nCould not import PySide2 as a Python module. Shotgun menu will not be available."
    + "\n\nPlease check the engine documentation for more information:"
    + "\nhttps://github.com/diegogarciahuerta/tk-blender/edit/master/README.md\n"
    + "-" * 80
)

try:
    from PySide2 import QtWidgets, QtCore

    PYSIDE2_IMPORTED = True
except ModuleNotFoundError:
    PYSIDE2_IMPORTED = False


class ShotgunConsoleLog(bpy.types.Operator):
    """
    A simple operator to log issues to the console.
    """

    bl_idname = "shotgun.logger"
    bl_label = "Shotgun Logger"

    message: bpy.props.StringProperty(name="message", description="message", default="")

    level: bpy.props.StringProperty(name="level", description="level", default="INFO")

    def execute(self, context):
        self.report({self.level}, self.message)
        return {"FINISHED"}


# based on
# https://github.com/vincentgires/blender-scripts/blob/master/scripts/addons/qtutils/core.py
class QtWindowEventLoop(bpy.types.Operator):
    """
    Integration of qt event loop within Blender
    """

    bl_idname = "screen.qt_event_loop"
    bl_label = "Qt Event Loop"

    def __init__(self):
        self._app = None
        self._timer = None
        self._event_loop = None

    def processEvents(self):
        self._event_loop.processEvents()
        self._app.sendPostedEvents(None, 0)

    def modal(self, context, event):
        if event.type == "TIMER":
            if self._app and not self.anyQtWindowsAreOpen():
                self.cancel(context)
                return {"FINISHED"}

            self.processEvents()
        return {"PASS_THROUGH"}

    def anyQtWindowsAreOpen(self):
        return any(w.isVisible() for w in QtWidgets.QApplication.topLevelWidgets())

    def execute(self, context):
        # create a QApplication if already does not exists
        self._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
            sys.argv
        )
        self._event_loop = QtCore.QEventLoop()

        # run modal
        wm = context.window_manager
        # self._timer = wm.event_timer_add(1 / 120, window=context.window)
        self._timer = wm.event_timer_add(0.001, window=context.window)
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """Remove event timer when stopping the operator."""
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


class TOPBAR_MT_shotgun(Menu):
    """
    Creates the Shotgun top level menu
    """

    bl_label = "Shotgun"
    bl_idname = "TOPBAR_MT_shotgun"

    def draw(self, context):
        import sgtk

        engine = sgtk.platform.current_engine()
        if engine:
            engine.display_menu()


def insert_main_menu(menu_class, before_menu_class):
    """
    This function allows adding a new menu into the top menu bar in Blender,
    inserting it before another menu specified.

    In order to be changes proof, this function collects the code for the
    Operator that creates the top level menus, and modifies it by using
    python AST (Abstract Syntax Trees), finds where the help menu is appended,
    and inserts a new AST node in between that represents our new menu.

    Then it is a matter of registering the class for Blender to recreate it's
    own top level menus with the additional

    A bit overkill, but the alternative was to copy&paste some Blender original
    code that could have changed from version to version. (if fact it did
    change from minor version to minor version while developing this engine.)

    """

    # This is an AST nodetree that represents the following code:
    # layout.menu("<menu_class.__name__>")
    # which will ultimately be inserted before the menu specified.
    sg_ast_expr = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="layout", ctx=ast.Load()), attr="menu", ctx=ast.Load()
            ),
            args=[ast.Str(s=menu_class.__name__)],
            keywords=[],
        )
    )

    # get the source code for the top menu bar menus
    code = inspect.getsource(bpy.types.TOPBAR_MT_editor_menus)
    code_ast = ast.parse(code)

    # find the `draw` method
    function_node = None
    for node in ast.walk(code_ast):
        if isinstance(node, ast.FunctionDef) and node.name == "draw":
            function_node = node
            break

    # find where the help menu is added, and insert ours right before it
    for i, node in enumerate(function_node.body):
        if isinstance(node, ast.Expr) and before_menu_class.__name__ in ast.dump(node):
            function_node.body.insert(i - 1, sg_ast_expr)
            break

    # make sure line numbers are fixed
    ast.fix_missing_locations(code_ast)

    # compile and execute the code
    code_ast_compiled = compile(code_ast, filename=__file__, mode="exec")
    exec(code_ast_compiled)

    # the newly create class is now within the local variables
    return locals()["TOPBAR_MT_editor_menus"]


# class TOPBAR_MT_editor_menus(Menu):
#     """
#     I could not find an easy way to simply add the menu into Blender's top
#     menubar.

#     So we use a bit of a hack, by recreating the the same as what blender does
#     to create it's own top level menus but adding the `Shotgun` menu right
#     before `help` menu.

#     Note that If the script to generate those menus was to change in Blender,
#     this would have to be update to reflect the same changes!
#     """
#     bl_idname = "TOPBAR_MT_editor_menus"
#     bl_label = ""

#     def draw(self, _context):
#         layout = self.layout

#         layout.menu("TOPBAR_MT_app", text="", icon='BLENDER')

#         layout.menu("TOPBAR_MT_file")
#         layout.menu("TOPBAR_MT_edit")

#         layout.menu("TOPBAR_MT_render")

#         layout.menu("TOPBAR_MT_window")
#         layout.menu("TOPBAR_MT_shotgun")
#         layout.menu("TOPBAR_MT_help")


def boostrap():
    # start the engine
    SGTK_MODULE_PATH = os.environ.get("SGTK_MODULE_PATH")
    if SGTK_MODULE_PATH and SGTK_MODULE_PATH not in sys.path:
        sys.path.insert(0, SGTK_MODULE_PATH)

    engine_startup_path = os.environ.get("SGTK_BLENDER_ENGINE_STARTUP")
    engine_startup = imp.load_source("sgtk_blender_engine_startup", engine_startup_path)

    # Fire up Toolkit and the environment engine.
    engine_startup.start_toolkit()


@persistent
def startup(dummy):
    bpy.ops.screen.qt_event_loop()
    boostrap()


@persistent
def error_importing_pyside2(*args):
    bpy.ops.shotgun.logger(level="ERROR", message=PYSIDE2_MISSING_MESSAGE)


def register():
    bpy.utils.register_class(ShotgunConsoleLog)

    if not PYSIDE2_IMPORTED:
        # bpy.app.timers.register(error_importing_pyside2, first_interval=5)
        load_factory_startup_post.append(error_importing_pyside2)
        return

    bpy.utils.register_class(QtWindowEventLoop)
    TOPBAR_MT_help = bpy.types.TOPBAR_MT_help
    TOPBAR_MT_editor_menus = insert_main_menu(
        TOPBAR_MT_shotgun, before_menu_class=TOPBAR_MT_help
    )
    bpy.utils.register_class(TOPBAR_MT_editor_menus)
    bpy.utils.register_class(TOPBAR_MT_shotgun)

    load_factory_startup_post.append(startup)


def unregister():
    bpy.utils.unregister_class(ShotgunConsoleLog)

    if not PYSIDE2_IMPORTED:
        return

    bpy.utils.unregister_class(TOPBAR_MT_shotgun)
