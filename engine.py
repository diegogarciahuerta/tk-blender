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


"""
A Blender engine for Tank.
https://www.blender.org/
"""

import os
import sys
import time
import atexit
import logging
import traceback

import tank
from tank.log import LogManager
from tank.platform import Engine
from tank.util import is_windows, is_linux, is_macos

import bpy
from bpy.app.handlers import persistent


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


ENGINE_NAME = "tk-blender"
ENGINE_NICE_NAME = "Shotgun Blender Engine"
APPLICATION_NAME = "Blender"

# env variable that control if to show the compatibility warning dialog
# when Blender software version is above the tested one.
SHOW_COMP_DLG = "SGTK_COMPATIBILITY_DIALOG_SHOWN"

# this is the absolute minimum Blender version for the engine to work. Actually
# the one the engine was developed originally under, so change it at your
# own risk if needed.
MIN_COMPATIBILITY_VERSION = 2.8


# Although the engine has logging already, this logger is needed for logging
# where an engine may not be present.
logger = LogManager.get_logger(__name__)


# logging functionality
def display_message(level, msg):
    t = time.asctime(time.localtime())
    print("%s | %s | %s | %s " % (t, level, ENGINE_NICE_NAME, msg))


def display_error(msg):
    display_message("Error", msg)


def display_warning(msg):
    display_message("Warning", msg)


def display_info(msg):
    display_message("Info", msg)


def display_debug(msg):
    if os.environ.get("TK_DEBUG") == "1":
        display_message("Debug", msg)


# methods to support the state when the engine cannot start up
# for example if a non-tank file is loaded in Blender we load the project
# context if exists, so we give a chance to the user to at least
# do the basics operations.


@persistent
def on_scene_event_callback(*args, **kwargs):
    """
    Callback that's run whenever a scene is saved or opened.
    """
    from sgtk.platform.qt import QtGui

    try:
        refresh_engine()
    except Exception as e:
        logger.exception("Could not refresh the engine; error: '%s'" % e)
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        message = ""
        message += (
            "Message: Shotgun encountered a problem changing the Engine's context.\n"
        )
        message += "Please contact support@shotgunsoftware.com\n\n"
        message += "Exception: %s - %s\n" % (exc_type, exc_value)
        message += "Traceback (most recent call last):\n"
        message += "\n".join(traceback.format_tb(exc_traceback))
        if QtGui.QApplication.instance():
            QtGui.QMessageBox.critical(None, ENGINE_NICE_NAME, message)

        print(message)


def setup_app_handlers():
    # make sure we only register once
    teardown_app_handlers()

    # register our callback on load and save
    bpy.app.handlers.load_post.append(on_scene_event_callback)
    bpy.app.handlers.save_post.append(on_scene_event_callback)

    # make sure we remove the callbacks on exit
    atexit.register(teardown_app_handlers)


def teardown_app_handlers():
    if refresh_engine in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_scene_event_callback)

    if refresh_engine in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_scene_event_callback)


def refresh_engine():
    """
    Refresh the current engine
    """

    logger.debug("Refreshing the engine")

    engine = tank.platform.current_engine()

    if not engine:
        # If we don't have an engine for some reason then we don't have
        # anything to do.
        logger.debug(
            "%s Refresh_engine | No currently initialized engine found; aborting the refresh of the engine\n"
            % APPLICATION_NAME
        )
        return

    scene_name = bpy.data.filepath

    if not scene_name or scene_name in ("", "Untitled.blend"):
        logger.debug("File has not been saved yet, aborting the refresh of the engine.")
        return

    # make sure path is normalized
    scene_name = os.path.abspath(scene_name)

    # we are going to try to figure out the context based on the
    # active document
    current_context = tank.platform.current_engine().context

    ctx = current_context

    # this file could be in another project altogether, so create a new
    # API instance.
    try:
        # and construct the new context for this path:
        tk = tank.sgtk_from_path(scene_name)
        logger.debug("Extracted sgtk instance: '%r' from path: '%r'", tk, scene_name)

    except tank.TankError:
        # could not detect context from path, will use the project context
        # for menus if it exists
        message = (
            "Shotgun %s Engine could not detect the context\n"
            "from the active document. Shotgun menus will be  \n"
            "stay in the current context '%s' "
            "\n" % (APPLICATION_NAME, ctx)
        )
        display_warning(message)
        return

    ctx = tk.context_from_path(scene_name, current_context)
    logger.debug(
        "Given the path: '%s' the following context was extracted: '%r'",
        scene_name,
        ctx,
    )

    # default to project context in worse case scenario
    if not ctx:
        project_name = engine.context.project.get("name")
        ctx = tk.context_from_entity_dictionary(engine.context.project)
        logger.debug(
            (
                "Could not extract a context from the current active project "
                "path, so we revert to the current project '%r' context: '%r'"
            ),
            project_name,
            ctx,
        )

    # Only change if the context is different
    if ctx != current_context:
        try:
            engine.change_context(ctx)
        except tank.TankError:
            message = (
                "Shotgun %s Engine could not change context\n"
                "to '%r'. Shotgun menu will be disabled!.\n"
                "\n" % (APPLICATION_NAME, ctx)
            )
            display_warning(message)
            engine.create_shotgun_menu(disabled=True)


class BlenderEngine(Engine):
    """
    Shotgun Toolkit engine for Blender.
    """

    def __init__(self, *args, **kwargs):
        """
        Engine Constructor
        """
        self._qt_app = None
        self._qt_app_main_window = None
        self._menu_generator = None

        Engine.__init__(self, *args, **kwargs)

    def show_message(self, msg, level="info"):
        """
        Displays a dialog with the message according to  the severity level
        specified.
        """
        from sgtk.platform.qt import QtGui, QtCore

        level_icon = {
            "info": QtGui.QMessageBox.Information,
            "error": QtGui.QMessageBox.Critical,
            "warning": QtGui.QMessageBox.Warning,
        }

        dlg = QtGui.QMessageBox()
        dlg.setIcon(level_icon[level])
        dlg.setText(msg)
        dlg.setWindowTitle(ENGINE_NICE_NAME)
        dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        dlg.show()
        dlg.exec_()

    def show_error(self, msg):
        """
        Displays an error dialog message
        """
        self.show_message(msg, level="error")

    def show_warning(self, msg):
        """
        Displays a warning dialog message
        """
        self.show_message(msg, level="warning")

    def show_info(self, msg):
        """
        Displays an informative dialog message
        """
        self.show_message(msg, level="info")

    @property
    def context_change_allowed(self):
        """
        Whether the engine allows a context change without the need for a
        restart.
        """
        return True

    @property
    def host_info(self):
        """
        :returns: A dictionary with information about the application hosting
                  his engine.

        The returned dictionary is of the following form on success:

            {
                "name": "Blender",
                "version": "2.8.1",
            }

        The returned dictionary is of following form on an error preventing
        the version identification.

            {
                "name": "Blender",
                "version: "unknown"
            }
        """

        host_info = {"name": "Blender", "version": "unknown"}
        try:
            host_info["version"] = bpy.app.version_string
        except Exception:
            pass
        return host_info

    def pre_app_init(self):
        """
        Initializes the Blender engine.
        """

        self.logger.debug("Initializing engine... %s", self)

        self.tk_blender = self.import_module("tk_blender")

        self.init_qt_app()

        """
        Runs after the engine is set up but before any apps have been
        initialized.
        """
        from tank.platform.qt import QtCore

        # unicode characters returned by the shotgun api need to be converted
        # to display correctly in all of the app windows
        # tell QT to interpret C strings as utf-8
        utf8 = QtCore.QTextCodec.codecForName("utf-8")
        QtCore.QTextCodec.setCodecForCStrings(utf8)
        self.logger.debug("set utf-8 codec for widget text")

    def init_engine(self):
        """
        Initializes the Blender engine.
        """
        self.logger.debug("%s: Initializing...", self)

        # check that we are running a supported OS
        if not any([is_windows(), is_linux(), is_macos()]):
            raise tank.TankError(
                "The current platform is not supported!"
                " Supported platforms "
                "are Mac, Linux 64 and Windows 64."
            )

        # check that we are running an ok version of Blender
        build_version = bpy.app.version
        app_ver = float(".".join(map(str, build_version[:2])))

        if app_ver < MIN_COMPATIBILITY_VERSION:
            msg = (
                "Shotgun integration is not compatible with %s versions older than %s"
                % (
                    APPLICATION_NAME,
                    MIN_COMPATIBILITY_VERSION,
                )
            )
            self.show_error(msg)
            raise tank.TankError(msg)

        if app_ver > MIN_COMPATIBILITY_VERSION:
            # show a warning that this version of Blender isn't yet fully tested
            # with Shotgun:
            msg = (
                "The Shotgun Pipeline Toolkit has not yet been fully "
                "tested with %s %s.  "
                "You can continue to use Toolkit but you may experience "
                "bugs or instability."
                "\n\n" % (APPLICATION_NAME, app_ver)
            )

            # determine if we should show the compatibility warning dialog:
            show_warning_dlg = self.has_ui and SHOW_COMP_DLG not in os.environ

            if show_warning_dlg:
                # make sure we only show it once per session
                os.environ[SHOW_COMP_DLG] = "1"

                min_ver = self.get_setting("compatibility_dialog_min_version")
                if build_version[0] < min_ver:
                    show_warning_dlg = False

            if show_warning_dlg:
                # Note, title is padded to try to ensure dialog isn't insanely
                # narrow!
                self.show_info(msg)

            # always log the warning to the script editor:
            self.logger.warning(msg)

            # In the case of Windows, we have the possibility of locking up if
            # we allow the PySide shim to import QtWebEngineWidgets.
            # We can stop that happening here by setting the following
            # environment variable.

            # Note that prior PyQt5 v5.12 this module existed, after that it has
            # been separated and would not cause any issues.
            # https://www.riverbankcomputing.com/software/pyqtwebengine/intro
            if is_windows():
                self.logger.debug(
                    "This application on Windows can deadlock if QtWebEngineWidgets "
                    "is imported. Setting "
                    "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT=1..."
                )
                os.environ["SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT"] = "1"

        # default menu name is Shotgun but this can be overriden
        # in the configuration to be Sgtk in case of conflicts
        self._menu_name = "Shotgun"
        if self.get_setting("use_sgtk_as_menu_name", False):
            self._menu_name = "Sgtk"

        if self.get_setting("automatic_context_switch", True):
            # need to watch some scene events in case the engine needs rebuilding:
            setup_app_handlers()
            self.logger.debug("Registered open and save callbacks.")

    def create_shotgun_menu(self, disabled=False):
        """
        Creates the main shotgun menu in Blender.
        Note that this only creates the menu, not the child actions
        :return: bool
        """

        # only create the shotgun menu if not in batch mode and menu doesn't
        # already exist
        if self.has_ui:
            self.logger.debug("Creating shotgun menu...")
            tk_blender = self.import_module("tk_blender")
            self._menu_generator = tk_blender.MenuGenerator(self, self._menu_name)
            self._menu_generator.create_menu(disabled=disabled)

        return False

    def display_menu(self, pos=None):
        """
        Shows the engine Shotgun menu.
        """
        if self._menu_generator:
            self._menu_generator.show(pos)

    def init_qt_app(self):
        """
        Initializes if not done already the QT Application for the engine.
        """

        """
        Ensure the QApplication is initialized
        """
        from sgtk.platform.qt import QtGui

        self._qt_app = QtGui.QApplication.instance()
        self._qt_app.setWindowIcon(QtGui.QIcon(self.icon_256))
        self._qt_app.setQuitOnLastWindowClosed(False)
        self._qt_app.setQuitOnLastWindowClosed(False)

        if self._qt_app_main_window is None:
            self.log_debug("Initializing main QApplication...")

            self._qt_app_main_window = QtGui.QMainWindow()

            # parent the main window under the Blender main window
            if is_windows():
                import ctypes

                hwnd = ctypes.windll.user32.GetActiveWindow()
                if hwnd:
                    self._qt_app_main_window.create(hwnd)

            self._qt_app_central_widget = QtGui.QWidget()
            self._qt_app_main_window.setCentralWidget(self._qt_app_central_widget)

        # set up the dark style
        self._initialize_dark_look_and_feel()

        # try to set the font size the same as Blender
        text_size = 9
        if len(bpy.context.preferences.ui_styles) > 0:
            self.log_debug("Applying Blender settings to QApplication style...")
            text_size = (
                bpy.context.preferences.ui_styles[0].widget.points - 2
            )  # MAGIC NUMBER TOTALLY CHOSEN BY EYE

        ui_scale = bpy.context.preferences.system.ui_scale
        text_size *= ui_scale
        self._qt_app.setStyleSheet(
            f""".QMenu {{ font-size: {text_size}pt; }}
                .QWidget {{ font-size: {text_size}pt; }}"""
        )

        self.logger.debug("QT Application: %s" % self._qt_app_main_window)

    def post_app_init(self):
        """
        Called when all apps have initialized
        """
        tank.platform.engine.set_current_engine(self)

        # create the shotgun menu
        self.create_shotgun_menu()

        # let's close the windows created by the engine before exiting the
        # application
        from sgtk.platform.qt import QtGui

        app = QtGui.QApplication.instance()
        app.aboutToQuit.connect(self.destroy_engine)

        # Run a series of app instance commands at startup.
        self._run_app_instance_commands()

    def post_context_change(self, old_context, new_context):
        """
        Runs after a context change. The Blender event watching will
        be stopped and new callbacks registered containing the new context
        information.

        :param old_context: The context being changed away from.
        :param new_context: The new context being changed to.
        """

        if self.get_setting("automatic_context_switch", True):
            setup_app_handlers()

            # finally create the menu with the new context if needed
            if old_context != new_context:
                self.create_shotgun_menu()

            self.sgtk.execute_core_hook_method(
                tank.platform.constants.CONTEXT_CHANGE_HOOK,
                "post_context_change",
                previous_context=old_context,
                current_context=new_context,
            )

    def _run_app_instance_commands(self):
        """
        Runs the series of app instance commands listed in the
        'run_at_startup' setting of the environment configuration YAML file.
        """

        # Build a dictionary mapping app instance names to dictionaries of
        # commands they registered with the engine.
        app_instance_commands = {}
        for (cmd_name, value) in self.commands.items():
            app_instance = value["properties"].get("app")
            if app_instance:
                # Add entry 'command name: command function' to the command
                # dictionary of this app instance.
                cmd_dict = app_instance_commands.setdefault(
                    app_instance.instance_name, {}
                )
                cmd_dict[cmd_name] = value["callback"]

        # Run the series of app instance commands listed in the
        # 'run_at_startup' setting.
        for app_setting_dict in self.get_setting("run_at_startup", []):
            app_instance_name = app_setting_dict["app_instance"]

            # Menu name of the command to run or '' to run all commands of the
            # given app instance.
            setting_cmd_name = app_setting_dict["name"]

            # Retrieve the command dictionary of the given app instance.
            cmd_dict = app_instance_commands.get(app_instance_name)

            if cmd_dict is None:
                self.logger.warning(
                    "%s configuration setting 'run_at_startup' requests app"
                    " '%s' that is not installed.",
                    self.name,
                    app_instance_name,
                )
            else:
                if not setting_cmd_name:
                    # Run all commands of the given app instance.
                    for (cmd_name, command_function) in cmd_dict.items():
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                else:
                    # Run the command whose name is listed in the
                    # 'run_at_startup' setting.
                    command_function = cmd_dict.get(setting_cmd_name)
                    if command_function:
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                    else:
                        known_commands = ", ".join("'%s'" % name for name in cmd_dict)
                        self.logger.warning(
                            "%s configuration setting 'run_at_startup' "
                            "requests app '%s' unknown command '%s'. "
                            "Known commands: %s",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                            known_commands,
                        )

    def destroy_engine(self):
        """
        Let's close the windows created by the engine before exiting the
        application
        """
        self.logger.debug("%s: Destroying...", self)
        self.close_windows()

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through
        show_dialog & show_modal.
        """
        return self._qt_app_main_window

    @property
    def has_ui(self):
        """
        Detect and return if Blender is running in batch mode
        """
        return not bpy.app.background

    def _emit_log_message(self, handler, record):
        """
        Called by the engine to log messages.
        All log messages from the toolkit logging namespace will be passed to
        this method.

        :param handler: Log handler that this message was dispatched from.
                        Its default format is "[levelname basename] message".
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Standard python logging record.
        :type record: :class:`~python.logging.LogRecord`
        """
        # Give a standard format to the message:
        #     Shotgun <basename>: <message>
        # where "basename" is the leaf part of the logging record name,
        # for example "tk-multi-shotgunpanel" or "qt_importer".
        if record.levelno < logging.INFO:
            formatter = logging.Formatter("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter("Shotgun %(basename)s: %(message)s")

        msg = formatter.format(record)

        # Select Blender display function to use according to the logging
        # record level.
        if record.levelno >= logging.ERROR:
            fct = display_error
        elif record.levelno >= logging.WARNING:
            fct = display_warning
        elif record.levelno >= logging.INFO:
            fct = display_info
        else:
            fct = display_debug

        # Display the message in Blender script editor in a thread safe manner.
        self.async_execute_in_main_thread(fct, msg)

    def close_windows(self):
        """
        Closes the various windows (dialogs, panels, etc.) opened by the
        engine.
        """

        # Make a copy of the list of Tank dialogs that have been created by the
        # engine and are still opened since the original list will be updated
        # when each dialog is closed.
        opened_dialog_list = self.created_qt_dialogs[:]

        # Loop through the list of opened Tank dialogs.
        for dialog in opened_dialog_list:
            dialog_window_title = dialog.windowTitle()
            try:
                # Close the dialog and let its close callback remove it from
                # the original dialog list.
                self.logger.debug("Closing dialog %s.", dialog_window_title)
                dialog.close()
            except Exception as exception:
                traceback.print_exc()
                self.logger.error(
                    "Cannot close dialog %s: %s", dialog_window_title, exception
                )
