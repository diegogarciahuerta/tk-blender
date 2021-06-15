'''
blender_software_info
---------------------

This module can be executed using the blender executables --python arg like so:

blender --background --python blender_software_info.py

It outputs json to stdout containing info about the blender install. Here is
a minimal example that calls blender_software_info.py and extracts the json
data using Python's regex module.

:: python

    import json
    import re
    import subprocess

    try:
        output = subprocess.check_output(
            'blender --background --python blender_software_info.py',
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True,
        )
        match = re.search(r'<json>(.*)</json>', output)
        software_info = json.loads(match.group(1))
        print('Blender Software Info:')
        print('    version: ' + software_info['version'])
        print('    user_scripts: ' + software_info['user_scripts'])
    except subprocess.CalledProcessError as e:
        print('Failed to get software info from blender executable: %s' % e)

This script is used in tk-blender's startup.py to find the appropriate
BLENDER_USER_SCRIPTS directory in BlenderLauncher._install_shotgun_menu_py.
'''

import json
import bpy.app
import bpy.utils


def main():
    software_info = json.dumps({
        'version': bpy.app.version_string,
        'user_scripts': bpy.utils.script_path_user(),
    })
    print(f'<json>{software_info}</json>')


if __name__ == '__main__':
    main()
