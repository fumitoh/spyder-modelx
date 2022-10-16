# -*- coding: utf-8 -*-

# Copyright (c) 2018-2022 Fumito Hamamura <fumito.ham@gmail.com>

# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation version 3.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

# The source code contains parts copied and modified from Spyder project:
# https://github.com/spyder-ide/spyder
# See below for the original copyright notice.

#
# Copyright (c) Spyder Project Contributors
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

import spyder
try:
    from spyder.api.plugins import SpyderPluginWidget
except ImportError:
    from spyder.plugins import SpyderPluginWidget # Spyder3

from spyder.config.base import _

from qtpy.QtWidgets import QVBoxLayout

from spyder_modelx.widgets.mxanalyzer import MxAnalyzerWidget
from .stacked_mixin import MxStackedMixin


if spyder.version_info > (5,):

    # New plugin API since Spyder 5
    from spyder.api.plugins import SpyderDockablePlugin, Plugins
    from qtpy.QtGui import QIcon
    from spyder.api.widgets.main_widget import PluginMainWidget
    # from spyder_modelx.plugins.mxplugin import ModelxConfigPage

    class MxAnalyzerMainWidget(MxStackedMixin, PluginMainWidget):

        MX_WIDGET_CLASS = MxAnalyzerWidget

        def __init__(self, name=None, plugin=None, parent=None):
            PluginMainWidget.__init__(self, name, plugin, parent)
            MxStackedMixin.__init__(self, parent=parent)

            # Layout
            layout = QVBoxLayout()
            layout.addWidget(self.stack)
            self.setLayout(layout)

            self.ipyconsole = plugin.get_plugin(Plugins.IPythonConsole)

        # --- API: methods to define or override
        # ------------------------------------------------------------------------
        def get_title(self):
            """
            Return the title that will be displayed on dockwidget or window title.
            """
            return _('MxAnalyzer')

        def setup(self):
            """
            Create widget actions, add to menu and other setup requirements.
            """
            pass

        def update_actions(self):
            """
            Update the state of exposed actions.

            Exposed actions are actions created by the self.create_action method.
            """
            pass

    class MxAnalyzerPlugin(SpyderDockablePlugin):
        """modelx sub-plugin.

        This plugin in registered by the modelx main plugin.
        """

        NAME = 'mxanalyzer'
        WIDGET_CLASS = MxAnalyzerMainWidget
        REQUIRES = [Plugins.IPythonConsole, 'modelx_plugin']
        CONF_SECTION = 'modelx'
        CONF_FILE = False

        # -------------------------------------------------------------------
        # --- API: Mandatory methods to define ------------------------------

        # For breaking change. see https://github.com/spyder-ide/spyder/issues/16966
        if spyder.version_info > (5, 2):

            @staticmethod
            def get_name():
                """
                Return the plugin localized name.

                Returns
                -------
                str
                    Localized name of the plugin.

                Notes
                -----
                This is a method to be able to update localization without a restart.
                """
                return _('MxAnalyzer')

        else:
            def get_name(self):
                """
                Return the plugin localized name.

                Returns
                -------
                str
                    Localized name of the plugin.

                Notes
                -----
                This is a method to be able to update localization without a restart.
                """
                return _('MxAnalyzer')

        def get_description(self):
            """
            Return the plugin localized description.

            Returns
            -------
            str
                Localized description of the plugin.

            Notes
            -----
            This is a method to be able to update localization without a restart.
            """
            return _('Widget for tracing modelx node dependency')

        def get_icon(self):
            """
            Return the plugin associated icon.

            Returns
            -------
            QIcon
                QIcon instance
            """
            return QIcon()

        def register(self):
            """
            Setup and register plugin in Spyder's main window and connect it to
            other plugins.
            """
            self.get_plugin('modelx_plugin').get_container().set_child_plugin('analyzer', self.get_container())
        # -------------------------------------------------------------------

        # register renamed to on_initialize from Spyder 5.1
        def on_initialize(self):
            """
            Setup and register plugin in Spyder's main window and connect it to
            other plugins.
            """
            self.get_plugin('modelx_plugin').get_container().set_child_plugin('analyzer', self.get_container())


else:
    class MxAnalyzerPlugin(MxStackedMixin, SpyderPluginWidget):
        """modelx sub-plugin.

        This plugin in registered by the modelx main plugin.
        """

        CONF_SECTION = 'modelx_analyzer'
        MX_WIDGET_CLASS = MxAnalyzerWidget
        CONF_FILE = False

        def __init__(self, parent=None):

            SpyderPluginWidget.__init__(self, parent)
            MxStackedMixin.__init__(self, parent)

            # Layout
            layout = QVBoxLayout()
            layout.addWidget(self.stack)
            if spyder.version_info > (4,):
                self.options_button.setVisible(False)
            self.setLayout(layout)

            if spyder.version_info < (4,):
                # Initialize plugin
                self.initialize_plugin()

        # --- SpyderPluginWidget API ----------------------------------------------
        def get_plugin_title(self):
            """Return widget title."""
            return 'MxAnalyzer'

        def get_focus_widget(self):
            """Return the widget to give focus to."""
            return self.current_widget()

        def refresh_plugin(self):
            """Refresh MxExplorer widget."""
            pass

        def get_plugin_actions(self):
            """Return a list of actions related to plugin."""
            return []

        def register_plugin(self):
            """Register plugin in Spyder's main window."""
            if spyder.version_info < (4,):
                self.main.add_dockwidget(self)
            else:
                self.add_dockwidget()

        def on_first_registration(self):
            """Action to be performed on first plugin registration."""
            self.main.tabify_plugins(self.main.help, self)

        def apply_plugin_settings(self, options):
            """Apply configuration file's plugin settings."""
            pass
