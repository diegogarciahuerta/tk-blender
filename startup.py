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


import json
import os
import re
import shutil
import subprocess
import sys

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


class BlenderLauncher(SoftwareLauncher):
    """
    Handles launching Blender executables. Automatically starts up
    a tk-blender engine with the current context in the new session
    of Blender.
    """

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {"version": r"\d.\d+(.\d*)*"}

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string.

    # Blender can be installed in different locations, since we cannot predict
    # where it will be located, we resort to letting the user define an
    # environment variable that points to the folder location where the
    # executable is located, that way we cover all cases. The disadvantage of
    # this is that we do not get a version number out of it.
    EXECUTABLE_TEMPLATES = {
        "darwin": [
            "$BLENDER_BIN_DIR/Blender",
            "/Library/Application Support/Blender.app/Contents/MacOS/Blender",
        ],
        "win32": [
            "$BLENDER_BIN_DIR/blender.exe",
            "$USERPROFILE/AppData/Roaming/Blender Foundation/Blender/{version}/blender.exe",
            "C:/Program Files/Blender Foundation/Blender {version}/blender.exe",
            "C:/Program Files/Blender Foundation/Blender/blender.exe",
        ],
        "linux2": ["$BLENDER_BIN_DIR/blender", "/usr/share/blender/blender"],
    }

    @property
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        """
        return "2.8"

    def _get_blender_software_info(self, exec_path):
        '''Get the default base path for BLENDER_USER_SCRIPTS.'''
        blender_software_info = os.path.join(
            self.disk_location,
            'blender_software_info.py',
        )
        output = subprocess.check_output(
            '"%s" --background --python %s' %
            (exec_path, blender_software_info),
            shell=True,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        if output:
            match = re.search(r'<json>(.*)</json>', output)
            if match:
                return json.loads(match.group(1))

    def _get_blender_user_scripts(self, exec_path):
        '''Get the path to current user scripts directory.'''

        user_scripts = os.getenv('BLENDER_USER_SCRIPTS')
        if user_scripts:
            return user_scripts

        # If BLENDER_USER_SCRIPTS is not set, get info from executable
        software_info = self._get_blender_software_info(exec_path)
        if software_info:
            return software_info['user_scripts']

    def _install_shotgun_menu_py(self, user_scripts):
        source = os.path.join(
            self.disk_location,
            'resources',
            'scripts',
            'startup',
            'Shotgun_menu.py',
        )
        target = os.path.join(
            user_scripts,
            'startup',
            'Shotgun_menu.py'
        )
        target_dir = os.path.dirname(target)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)

        if os.path.isfile(target):
            source_mtime = os.path.getmtime(source)
            target_mtime = os.path.getmtime(target)
            if source_mtime <= target_mtime:
                self.logger.debug(
                    'Found existing Shotgun_menu.py in %s' % target_dir
                )
                return
            else:
                self.logger.debug('Update Shotgun_menu.py in %s' % target_dir)
                os.remove(target)
        else:
            self.logger.debug('Install Shotgun_menu.py in %s' % target_dir)

        shutil.copy2(source, target)


    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch Blender in that will automatically
        load Toolkit and the tk-blender engine when Blender starts.

        :param str exec_path: Path to Blender executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on
                                 launch.
        :returns: :class:`LaunchInformation` instance
        """
        required_env = {}

        # Copy Shotgun_menu.py to current users BLENDER_USER_SCRIPTS directory
        try:
            user_scripts = self._get_blender_user_scripts(exec_path)
            if user_scripts:
                self._install_shotgun_menu_py(user_scripts)
        except Exception as e:
            self.logger.exception('Failed to install Shotgun_menu.py')

        if not os.environ.get("PYSIDE2_PYTHONPATH"):
            pyside2_python_path = os.path.join(self.disk_location, "python", "ext")
            required_env["PYSIDE2_PYTHONPATH"] = pyside2_python_path

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.logger.debug(
            "Preparing Blender Launch via Toolkit Classic methodology ..."
        )

        required_env["SGTK_MODULE_PATH"] = sgtk.get_sgtk_module_path().replace(
            "\\", "/"
        )

        engine_startup_path = os.path.join(
            self.disk_location, "startup", "bootstrap.py"
        )

        required_env["SGTK_BLENDER_ENGINE_STARTUP"] = engine_startup_path
        required_env["SGTK_BLENDER_ENGINE_PYTHON"] = sys.executable.replace("\\", "/")

        required_env["SGTK_ENGINE"] = self.engine_name
        required_env["SGTK_CONTEXT"] = sgtk.context.serialize(self.context)

        if file_to_open:
            # Add the file name to open to the launch environment
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)

    ###########################################################################
    # private methods

    def _icon_from_engine(self):
        """
        Use the default engine icon as blender does not supply
        an icon in their software directory structure.

        :returns: Full path to application icon as a string or None.
        """

        # the engine icon
        engine_icon = os.path.join(self.disk_location, "icon_256.png")
        return engine_icon

    def scan_software(self):
        """
        Scan the filesystem for blender executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug("Scanning for Blender executables...")

        supported_sw_versions = []
        for sw_version in self._find_software():
            (supported, reason) = self._is_supported(sw_version)
            if supported:
                supported_sw_versions.append(sw_version)
            else:
                self.logger.debug(
                    "SoftwareVersion %s is not supported: %s" % (sw_version, reason)
                )

        return supported_sw_versions

    def _find_software(self):
        """
        Find executables in the default install locations.
        """

        # all the executable templates for the current OS
        executable_templates = self.EXECUTABLE_TEMPLATES.get(sys.platform, [])

        # all the discovered executables
        sw_versions = []

        # Here we account for extra arguments passed to the blender command line
        # this allows a bit of flexibility without having to fork the whole
        # engine just for this reason.
        # Unfortunately this cannot be put in the engine.yml as I would like
        # to because the engine class has not even been instantiated yet.
        extra_args = os.environ.get("SGTK_BLENDER_CMD_EXTRA_ARGS")

        # Extract all software versions matching the executable templates.
        for executable_template in executable_templates:
            executable_template = os.path.expanduser(executable_template)
            executable_template = os.path.expandvars(executable_template)

            self.logger.debug("Processing template %s", executable_template)

            executable_matches = self._glob_and_match(
                executable_template, self.COMPONENT_REGEX_LOOKUP
            )

            for (executable_path, key_dict) in executable_matches:

                # Get the version from the key_dict returned by the
                # _glob_and_match method. If we don't match a version, try
                # harder using _get_executable_version. Default to " " in
                # case no version is detected from the executable_path.
                executable_version = key_dict.get(
                    "version",
                    self._get_executable_version(executable_path, " ")
                )

                args = []
                if extra_args:
                    args.append(extra_args)

                sw_versions.append(
                    SoftwareVersion(
                        executable_version,
                        "Blender",
                        executable_path,
                        icon=self._icon_from_engine(),
                        args=args,
                    )
                )

        return sw_versions

    def _get_executable_version(self, exec_path, default=None):
        '''Attempt to find the best possible version number from a Blender
        executable path.'''

        # On Windows and in custom installs the version may be in the exec_path
        match = re.search(self.COMPONENT_REGEX_LOOKUP['version'], exec_path)
        if match:
            return match.group(0)

        # On mac we may find a version folder in the apps Contents/Resources
        if 'Blender.app' in exec_path:
            app_dir = executable_path.split('Blender.app')[0] + 'Blender.app'
            resources_dir = os.path.join(app_dir, 'Contents', 'Resources')

            if not os.path.isdir(resources_dir):
                return default

            for file in os.listdir(resources_dir):
                if re.match(self.COMPONENT_REGEX_LOOKUP['version'], file):
                    return file

        # On Linux we may find a version folder next to the executable
        app_dir = os.path.dirname(exec_path)
        if not os.path.isdir(app_dir):
            return default

        for file in os.listdir(app_dir):
            if re.match(self.COMPONENT_REGEX_LOOKUP['version'], file):
                return file

        return default
