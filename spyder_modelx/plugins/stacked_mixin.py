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

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QStackedWidget, QWidget, QLabel
import spyder


class MxStackedMixin:
    """Mixin to Plugin classes to stacked child widgets.

    The stacked child widgets are of MX_WIDGET_CLASS.
    Each of the stacked child widgets is connected to each MxShellWidget.

    """
    MX_WIDGET_CLASS = None  # To be defined in sub class

    def __init__(self, parent):

        self.main = parent  # Spyder3

        # Widgets
        self.stack = QStackedWidget(self)
        self.shellwidgets = {}

        # Fallback widget when no MxConsole available.
        # Spyder 4 output internal error message without this.
        self.blankwidget = QLabel(text="No MxConsole Available")
        self.blankwidget.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.blankwidget)

        # On active tab in IPython console change
        if spyder.version_info > (5, 2):
            self.main.ipyconsole.get_widget().tabwidget.currentChanged.connect(
                self.on_ipyconsole_current_changed)
        else:
            self.main.ipyconsole.tabwidget.currentChanged.connect(
                self.on_ipyconsole_current_changed)

    # ----- Stack accesors ----------------------------------------------------
    # Modified from https://github.com/spyder-ide/spyder/blob/v3.3.2/spyder/plugins/variableexplorer.py#L140

    def set_current_widget(self, mxwidget):
        self.stack.setCurrentWidget(mxwidget)
        # self.refresh_actions()
        if spyder.version_info < (5,):
            mxwidget.setup_options_button()

    def current_widget(self):
        return self.stack.currentWidget()

    def count(self):
        return self.stack.count()

    def remove_widget(self, mxwidget):
        self.stack.removeWidget(mxwidget)

    def add_widget(self, mxwidget):
        self.stack.addWidget(mxwidget)

    # ----- Public API --------------------------------------------------------
    # Modified from https://github.com/spyder-ide/spyder/blob/v3.3.2/spyder/plugins/variableexplorer.py#L156

    def add_shellwidget(self, shellwidget):
        """
        Register shell with variable explorer.

        This function opens a new NamespaceBrowser for browsing the variables
        in the shell.
        """
        shellwidget_id = id(shellwidget)
        if shellwidget_id not in self.shellwidgets:
            if spyder.version_info < (4,) or spyder.version_info > (5,):
                mxwidget = self.MX_WIDGET_CLASS(self, options_button=None)
            else:
                self.options_button.setVisible(True)
                mxwidget = self.MX_WIDGET_CLASS(
                        self, options_button=self.options_button)
            mxwidget.set_shellwidget(shellwidget)
            # analyzer.sig_option_changed.connect(self.change_option)
            # analyzer.sig_free_memory.connect(self.free_memory)
            self.add_widget(mxwidget)
            self.shellwidgets[shellwidget_id] = mxwidget
            self.set_shellwidget_from_id(shellwidget_id)
            return mxwidget

    def remove_shellwidget(self, shellwidget_id):
        # If shellwidget_id is not in self.shellwidgets, it simply means
        # that shell was not a Python-based console (it was a terminal)
        if shellwidget_id in self.shellwidgets:
            mxwidget = self.shellwidgets.pop(shellwidget_id)
            self.remove_widget(mxwidget)
            mxwidget.close()

    def set_shellwidget_from_id(self, shellwidget_id):
        if shellwidget_id in self.shellwidgets:
            mxwidget = self.shellwidgets[shellwidget_id]
            self.set_current_widget(mxwidget)

    def on_ipyconsole_current_changed(self):
        # Slot like IPythonConsole.reflesh_plugin
        if spyder.version_info > (5, 2):
            client = self.main.ipyconsole.get_widget().tabwidget.currentWidget()
        else:
            client = self.main.ipyconsole.tabwidget.currentWidget()
        if client:
            sw = client.shellwidget
            self.set_shellwidget_from_id(id(sw))
