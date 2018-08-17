# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Fumito Hamamura
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""modelx Plugin."""

from qtpy.QtWidgets import QVBoxLayout

try:
    from spyder.api.plugins import SpyderPluginWidget
except ImportError:
    from spyder.plugins import SpyderPluginWidget # Spyder3
try:
    from spyder.api.preferences import PluginConfigPage
except ImportError:
    from spyder.plugins.configdialog import PluginConfigPage # Spyder3
from .widgets.modelxgui import ModelxWidget


class ModelxConfigPage(PluginConfigPage):
    """modelx plugin preferences."""

    def setup_page(self):
        pass


class ModelxPlugin(SpyderPluginWidget):
    """modelx plugin."""
    CONF_SECTION = 'modelx'

    CONFIGWIDGET_CLASS = ModelxConfigPage


    def __init__(self, parent=None):
        SpyderPluginWidget.__init__(self, parent)
        self.main = parent # Spyder3

        # Create widget and add to dockwindow
        self.widget = ModelxWidget(self.main)
        layout = QVBoxLayout()
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # Initialize plugin
        self.initialize_plugin()

    # --- SpyderPluginWidget API ----------------------------------------------
    def get_plugin_title(self):
        """Return widget title."""
        return "modelx"

    def get_focus_widget(self):
        """Return the widget to give focus to."""
        return self.widget

    def refresh_plugin(self):
        """Refresh ModelxWidget widget."""
        pass

    def get_plugin_actions(self):
        """Return a list of actions related to plugin."""
        return []

    def register_plugin(self):
        """Register plugin in Spyder's main window."""
        self.main.add_dockwidget(self)

    def on_first_registration(self):
        """Action to be performed on first plugin registration."""
        self.main.tabify_plugins(self.main.help, self)

    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings."""
        pass
