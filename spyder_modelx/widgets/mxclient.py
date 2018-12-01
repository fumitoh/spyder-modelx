# -*- coding: utf-8 -*-

# Copyright (c) 2017-2018 Fumito Hamamura <fumito.ham@gmail.com>

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

"""modelx Widget."""

from qtpy.QtCore import QTimer, Signal, Slot, Qt
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox, QAction,
                            QToolButton, QVBoxLayout, QWidget, QTreeView)
from spyder.config.base import _, debug_print
from spyder.widgets.ipythonconsole.client import ClientWidget
from spyder.widgets.mixins import SaveHistoryMixin
from spyder.widgets.browser import WebView
from spyder.utils import icon_manager as ima
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, DialogManager,
                                    MENU_SEPARATOR)

from spyder_modelx.widgets.mxshell import MxShellWidget


class MxClientWidget(ClientWidget):
    """Custom client widget for modelx

    The only difference from ClientWidget is its
    shell member being MxShellWidget
    """

    def __init__(self, plugin, id_,
                 history_filename, config_options,
                 additional_options, interpreter_versions,
                 connection_file=None, hostname=None,
                 menu_actions=None, slave=False,
                 external_kernel=False, given_name="MxConsole",
                 show_elapsed_time=False,
                 reset_warning=True):
        super(ClientWidget, self).__init__(plugin)
        SaveHistoryMixin.__init__(self, history_filename)

        # --- Init attrs
        self.id_ = id_
        self.connection_file = connection_file
        self.hostname = hostname
        self.menu_actions = menu_actions
        self.slave = slave
        self.external_kernel = external_kernel
        self.given_name = given_name
        self.show_elapsed_time = show_elapsed_time
        self.reset_warning = reset_warning

        # --- Other attrs
        self.options_button = None
        self.stop_button = None
        self.reset_button = None
        self.stop_icon = ima.icon('stop')
        self.history = []
        self.allow_rename = True
        self.stderr_dir = None

        # --- Widgets
        self.shellwidget = MxShellWidget(
            config=config_options,
            ipyclient=self,
            additional_options=additional_options,
            interpreter_versions=interpreter_versions,
            external_kernel=external_kernel,
            local_kernel=True)
        self.infowidget = WebView(self)
        self.set_infowidget_font()
        self.loading_page = self._create_loading_page()
        self._show_loading_page()

        # Elapsed time
        self.time_label = None
        self.t0 = None
        self.timer = QTimer(self)

        # --- Layout
        vlayout = QVBoxLayout()
        toolbar_buttons = self.get_toolbar_buttons()

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.create_time_label())
        hlayout.addStretch(0)
        for button in toolbar_buttons:
            hlayout.addWidget(button)

        vlayout.addLayout(hlayout)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.addWidget(self.shellwidget)
        vlayout.addWidget(self.infowidget)
        self.setLayout(vlayout)

        # --- Exit function
        self.exit_callback = lambda: plugin.close_client(client=self)

        # --- Dialog manager
        self.dialog_manager = DialogManager()

        # Show timer
        self.update_time_label_visibility()

        # Set up modelx browser
        self.shellwidget.set_mxexplorer(plugin.widget)
        self.shellwidget.set_mxdataview(plugin.dataview.widget,
                                        plugin.dataview.exprbox)
        self.shellwidget.set_mxcodelist(plugin.codelist)

    def get_name(self):
        """Return client name"""
        if self.given_name is None:
            # Name according to host
            if self.hostname is None:
                name = _("Console")
            else:
                name = self.hostname
            # Adding id to name
            client_id = self.id_['int_id'] + u'/' + self.id_['str_id']
            name = name + u' ' + client_id
        else:
            client_id = self.id_['int_id'] + u'/' + self.id_['str_id']
            name = self.given_name + u' ' + client_id
        return name
