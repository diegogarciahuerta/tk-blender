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
import bpy
import sgtk


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class BlenderSessionCollector(HookBaseClass):
    """
    Collector that operates on the blender session. Should inherit from the
    basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(BlenderSessionCollector, self).settings or {}

        # settings specific to this collector
        blender_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            }
        }

        # update the base settings with these settings
        collector_settings.update(blender_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Blender and parents a subtree of
        items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance

        """

        # create an item representing the current blender session
        item = self.collect_current_blender_session(settings, parent_item)
        self._collect_session_geometry(item)

    def _collect_session_geometry(self, parent_item):
        """
        Creates items for session geometry to be exported.
        :param parent_item: Parent Item instance
        """

        geo_item = parent_item.create_item(
            "blender.session.geometry", "Geometry", "All Session Geometry"
        )

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "geometry.png")

        geo_item.set_icon_from_path(icon_path)

    def collect_current_blender_session(self, settings, parent_item):
        """
        Creates an item that represents the current blender session.

        :param parent_item: Parent Item instance

        :returns: Item of type blender.session
        """

        publisher = self.parent

        # get the path to the current file
        path = bpy.data.filepath

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Blender Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "blender.session", "Blender Session", display_name
        )

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "blender.png")
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so
        # that it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:

            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            session_item.properties["publish_type"] = "Blender Project File"
            self.logger.debug("Work template defined for Blender collection.")

        self.logger.info("Collected current Blender scene")

        return session_item
