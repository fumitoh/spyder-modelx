# -*- coding: utf-8 -*-

# Copyright (c) 2018-2019 Fumito Hamamura <fumito.ham@gmail.com>

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

import sys

from qtpy.QtWidgets import QVBoxLayout

import spyder
try:
    from spyder.api.plugins import SpyderPluginWidget
except ImportError:
    from spyder.plugins import SpyderPluginWidget  # Spyder3

from spyder_modelx.widgets.mxdataview import MxDataViewWidget
from .stacked_mixin import MxStackedMixin


class MxDataViewPlugin(MxStackedMixin, SpyderPluginWidget):
    """modelx sub-plugin.

    This plugin in registered by the modelx main plugin.
    """

    CONF_SECTION = 'modelx'
    MX_WIDGET_CLASS = MxDataViewWidget

    def __init__(self, parent=None):

        SpyderPluginWidget.__init__(self, parent)
        MxStackedMixin.__init__(self, parent)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        if spyder.version_info > (4,):
            self.options_button.setVisible(False)
        self.setLayout(layout)
        self.setMinimumSize(400, 300)

        # Initialize plugin
        self.initialize_plugin()

    # --- SpyderPluginWidget API ----------------------------------------------
    def get_plugin_title(self):
        """Return widget title."""
        return 'MxDataView'

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
        self.main.add_dockwidget(self)

    def on_first_registration(self):
        """Action to be performed on first plugin registration."""
        self.main.tabify_plugins(self.main.help, self)

    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings."""
        pass
