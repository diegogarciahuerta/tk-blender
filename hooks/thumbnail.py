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
import tempfile
import uuid

from tank import Hook
from tank.platform.qt import QtGui


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


class ThumbnailHook(Hook):
    """
    Hook that can be used to provide a pre-defined thumbnail for the app
    """

    def execute(self, **kwargs):
        """
        Main hook entry point
        :returns:       String
                        Hook should return a file path pointing to the location
                        of a thumbnail file on disk that will be used.
                        If the hook returns None then the screenshot
                        functionality will be enabled in the UI.
        """
        # get the engine name from the parent object (app/engine/etc.)
        engine = self.parent.engine
        engine_name = engine.name

        # depending on engine:
        if engine_name == "tk-blender":
            return self._extract_blender_thumbnail()

        # default implementation does nothing
        return None

    def _extract_blender_thumbnail(self):
        """
        Render a thumbnail for the current window in Blender

        :returns:   The path to the thumbnail on disk
        """
        thumb = QtGui.QPixmap.grabWindow(QtGui.QApplication.desktop().winId())

        if thumb:
            # save the thumbnail
            temp_dir = tempfile.gettempdir()
            temp_filename = "sgtk_thumb_%s.jpg" % uuid.uuid4().hex
            jpg_thumb_path = os.path.join(temp_dir, temp_filename)
            thumb.save(jpg_thumb_path)

        return jpg_thumb_path
