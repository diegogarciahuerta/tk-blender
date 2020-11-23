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
from tank import Hook

import bpy


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


# let's put some color to these gray-ish UIs
ITEM_COLORS = {
    "library": "#e7a81d",
    "cache": "#a8e71d",
    "image": "#a81de7",
    "movieclip": "#1da8e7",
    "text": "#1de7a8",
    "sound": "#e71da8",
}


# represent the place where to query the different node types from
# note, no support for image sequences yet
COLLECTOR_DATA_TYPES = {
    "library": bpy.data.libraries,
    "cache": bpy.data.cache_files,
    "image": bpy.data.images,
    "movieclip": bpy.data.movieclips,
    "text": bpy.data.texts,
    "sound": bpy.data.sounds,
}


class BreakdownSceneItem(str):
    """
    Helper Class to store metadata per update item.

    tk-multi-breakdown requires item['node'] to be a str. This is what is displayed in
    the list of recognized items to update. We want to add metadata to each item
    as what we want to display as name is not the actual item to update.
    As a str is required we are forced to inherit from str instead of the more
    python friendly object + __repr__ magic method.
    """

    def __new__(cls, node, node_type):
        if node_type == "library":
            object_names = [obj.name for obj in node.users_id if obj]
            if len(object_names) > 5:
                object_names = object_names[0:4] + [". . ."] + [object_names[-1]]

            subtitle = "<br/>".join(object_names)

        elif node_type == "cache":
            paths = [
                object_path.path for object_path in node.object_paths if object_path
            ]
            if len(paths) > 5:
                paths = paths[0:4] + [". . ."] + [paths[-1]]

            subtitle = "<br/>".join(paths)

        elif node_type == "image":
            subtitle = node.name

        elif node_type == "movieclip":
            subtitle = node.name

        elif node_type == "sound":
            subtitle = node.name

        elif node_type == "text":
            subtitle = os.path.basename(node.filepath)

        text = (
            "<span style='color:%s'><b>%s</b></span>"
            "<br/><nobr><b><sub>%s</sub></b></nobr>"
            % (ITEM_COLORS[node_type], subtitle, node_type)
        )

        item = str.__new__(cls, text)
        item.node = node
        item.node_type = node_type

        return item


class BreakdownSceneOperations(Hook):
    """
    Breakdown operations for Blender.

    This implementation handles detection of blender file geometric,
    alembic, usd and texture nodes.
    """

    def scan_scene(self):
        """
        The scan scene method is executed once at startup and its purpose is
        to analyze the current scene and return a list of references that are
        to be potentially operated on.

        The return data structure is a list of dictionaries. Each scene
        reference that is returned should be represented by a dictionary with
        three keys:

        - "node": The filename attribute of the 'node' that is to be operated
           on. Most DCCs have a concept of a node, attribute, path or some other
           way to address a particular object in the scene.
        - "type": The object type that this is. This is later passed to the
           update method so that it knows how to handle the object.
        - "path": Path on disk to the referenced object.

        Toolkit will scan the list of items, see if any of the objects matches
        any templates and try to determine if there is a more recent version
        available. Any such versions are then displayed in the UI as out of
        date.
        """
        refs = []

        ref_paths = set()

        for node_type, collector_data_type in COLLECTOR_DATA_TYPES.items():
            for node in collector_data_type:
                # one exception for libraries, only collect the ones used
                # within the scene
                if node_type == "library":
                    if not node.users_id:
                        continue

                ref_path = node.filepath
                if ref_path not in ref_paths:
                    refs.append(
                        {
                            "type": node_type,
                            "path": ref_path,
                            "node": BreakdownSceneItem(node, node_type),
                        }
                    )
                ref_paths.add(ref_path)

        return refs

    def update(self, items):
        """
        Perform replacements given a number of scene items passed from the app.

        Once a selection has been performed in the main UI and the user clicks
        the update button, this method is called.

        The items parameter is a list of dictionaries on the same form as was
        generated by the scan_scene hook above. The path key now holds
        the that each attribute should be updated *to* rather than the current
        path.
        """

        engine = self.parent.engine

        for i in items:
            node_type = i["type"]
            new_path = i["path"]

            if node_type in COLLECTOR_DATA_TYPES.keys():
                node = i["node"].node

                engine.log_debug("Updating %s to: %s" % (node_type, new_path))
                node.filepath = new_path

                if hasattr(node, "reload"):
                    node.reload()
