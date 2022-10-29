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

"""modelx Widget."""

import time

from qtpy.QtCore import QTimer, Signal, Slot, Qt
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox, QAction,
                            QToolButton, QVBoxLayout, QWidget, QTreeView)
import spyder
from spyder.config.base import _, debug_print
if spyder.version_info < (4,):
    from spyder.widgets.ipythonconsole.client import ClientWidget
else:
    from spyder.plugins.ipythonconsole.widgets.client import (
        ClientWidget,
        CSS_PATH)

if spyder.version_info > (5, 2):
    from spyder.plugins.ipythonconsole.utils.stdfile import StdFile

from spyder.widgets.mixins import SaveHistoryMixin
from spyder.widgets.browser import WebView
from spyder.utils import icon_manager as ima
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, DialogManager,
                                    MENU_SEPARATOR)

from spyder_modelx.widgets.mxshell import MxShellWidget

try:
    time.monotonic  # time.monotonic new in 3.3
except AttributeError:
    time.monotonic = time.time


class MxClientWidget_5_3(ClientWidget):
    """Custom client widget for modelx

    The only difference from ClientWidget is its
    shell member being MxShellWidget
    """
    def __init__(self, parent, id_,
                 history_filename, config_options,
                 additional_options, interpreter_versions,
                 connection_file=None, hostname=None,
                 context_menu_actions=(),
                 menu_actions=None,
                 is_external_kernel=False,
                 is_spyder_kernel=True,
                 given_name='MxConsole',
                 give_focus=True,
                 options_button=None,
                 time_label=None,       # ~5.3.2
                 show_elapsed_time=False,
                 reset_warning=True,
                 ask_before_restart=True,
                 ask_before_closing=False,
                 css_path=None,
                 configuration=None,    # ~5.3.1
                 handlers={},
                 stderr_obj=None,
                 stdout_obj=None,
                 fault_obj=None,
                 initial_cwd=None   # 5.3.3~
                 ):
        super(ClientWidget, self).__init__(parent)
        SaveHistoryMixin.__init__(self, history_filename)

        # --- Init attrs
        self.container = parent
        self.id_ = id_
        self.connection_file = connection_file
        self.hostname = hostname
        self.menu_actions = menu_actions
        self.is_external_kernel = is_external_kernel
        self.given_name = given_name
        self.show_elapsed_time = show_elapsed_time
        self.reset_warning = reset_warning
        self.ask_before_restart = ask_before_restart
        self.ask_before_closing = ask_before_closing
        self.initial_cwd = initial_cwd  # 5.3.3~

        # --- Other attrs
        self.context_menu_actions = context_menu_actions
        self.time_label = time_label    # ~5.3.2
        self.options_button = options_button
        self.history = []
        self.allow_rename = True
        self.is_error_shown = False
        self.error_text = None
        self.restart_thread = None
        self.give_focus = give_focus

        if css_path is None:
            self.css_path = CSS_PATH
        else:
            self.css_path = css_path

        # --- Widgets
        self.shellwidget = MxShellWidget(
            config=config_options,
            ipyclient=self,
            additional_options=additional_options,
            interpreter_versions=interpreter_versions,
            is_external_kernel=is_external_kernel,
            is_spyder_kernel=is_spyder_kernel,
            handlers=handlers,
            local_kernel=True)
        self.infowidget = self.container.infowidget
        self.blank_page = self._create_blank_page()
        self.loading_page = self._create_loading_page()
        # To keep a reference to the page to be displayed
        # in infowidget
        self.info_page = None
        self._before_prompt_is_ready()

        # Elapsed time
        self.t0 = time.monotonic()
        self.timer = QTimer(self)

        # --- Layout
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.shellwidget)
        if self.infowidget is not None:
            self.layout.addWidget(self.infowidget)
        self.setLayout(self.layout)

        # --- Exit function
        self.exit_callback = lambda: self.container.close_client(client=self)

        # --- Dialog manager
        self.dialog_manager = DialogManager()

        # --- Standard files handling
        self.stderr_obj = stderr_obj
        self.stdout_obj = stdout_obj
        self.fault_obj = fault_obj
        self.std_poll_timer = None
        if self.stderr_obj is not None or self.stdout_obj is not None:
            self.std_poll_timer = QTimer(self)
            self.std_poll_timer.timeout.connect(self.poll_std_file_change)
            self.std_poll_timer.setInterval(1000)
            self.std_poll_timer.start()
            self.shellwidget.executed.connect(self.poll_std_file_change)

        self.start_successful = False

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


class MxClientWidget(ClientWidget):
    """Custom client widget for modelx

    The only difference from ClientWidget is its
    shell member being MxShellWidget
    """

    if spyder.version_info > (5, 2):
        def __init__(self, parent, id_,
                     history_filename, config_options,
                     additional_options, interpreter_versions,
                     connection_file=None, hostname=None,
                     context_menu_actions=(),
                     menu_actions=None,
                     is_external_kernel=False,
                     is_spyder_kernel=True,
                     given_name='MxConsole',
                     give_focus=True,
                     options_button=None,
                     time_label=None,
                     show_elapsed_time=False,
                     reset_warning=True,
                     ask_before_restart=True,
                     ask_before_closing=False,
                     css_path=None,
                     configuration=None,
                     handlers={},
                     std_dir=None):
            super(ClientWidget, self).__init__(parent)
            SaveHistoryMixin.__init__(self, history_filename)

            # --- Init attrs
            self.container = parent
            self.id_ = id_
            self.connection_file = connection_file
            self.hostname = hostname
            self.menu_actions = menu_actions
            self.is_external_kernel = is_external_kernel
            self.given_name = given_name
            self.show_elapsed_time = show_elapsed_time
            self.reset_warning = reset_warning
            self.ask_before_restart = ask_before_restart
            self.ask_before_closing = ask_before_closing

            # --- Other attrs
            self.context_menu_actions = context_menu_actions
            self.time_label = time_label
            self.options_button = options_button
            self.history = []
            self.allow_rename = True
            self.std_dir = std_dir
            self.is_error_shown = False
            self.error_text = None
            self.restart_thread = None
            self.give_focus = give_focus

            if css_path is None:
                self.css_path = CSS_PATH
            else:
                self.css_path = css_path

            # --- Widgets
            self.shellwidget = MxShellWidget(
                config=config_options,
                ipyclient=self,
                additional_options=additional_options,
                interpreter_versions=interpreter_versions,
                is_external_kernel=is_external_kernel,
                is_spyder_kernel=is_spyder_kernel,
                handlers=handlers,
                local_kernel=True,
                configuration=configuration)
            self.infowidget = self.container.infowidget
            self.blank_page = self._create_blank_page()
            self.loading_page = self._create_loading_page()
            # To keep a reference to the page to be displayed
            # in infowidget
            self.info_page = None
            self._before_prompt_is_ready()

            # Elapsed time
            self.t0 = time.monotonic()
            self.timer = QTimer(self)

            # --- Layout
            self.layout = QVBoxLayout()
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.addWidget(self.shellwidget)
            self.layout.addWidget(self.infowidget)
            self.setLayout(self.layout)

            # --- Exit function
            self.exit_callback = lambda: self.container.close_client(client=self)

            # --- Dialog manager
            self.dialog_manager = DialogManager()

            # --- Standard files handling
            self.stderr_obj = None
            self.stdout_obj = None
            self.fault_obj = None
            self.std_poll_timer = None
            if not self.is_external_kernel:
                # Cannot create std files for external kernels
                self.stderr_obj = StdFile(self.std_filename('.stderr'))
                self.stdout_obj = StdFile(self.std_filename('.stdout'))
                self.std_poll_timer = QTimer(self)
                self.std_poll_timer.timeout.connect(self.poll_std_file_change)
                self.std_poll_timer.setInterval(1000)
                self.std_poll_timer.start()
                self.shellwidget.executed.connect(self.poll_std_file_change)
            if self.hostname is None:
                # Cannot read file that is not on this computer
                self.fault_obj = StdFile(self.std_filename('.fault'))

    else:
        def __init__(self, plugin, id_,
                     history_filename, config_options,
                     additional_options, interpreter_versions,
                     connection_file=None, hostname=None,
                     menu_actions=None, slave=False,
                     external_kernel=False, given_name="MxConsole",
                     show_elapsed_time=False,
                     reset_warning=True,
                     **kwargs):
            super(ClientWidget, self).__init__(plugin)
            SaveHistoryMixin.__init__(self, history_filename)

            # --- Init attrs
            self.plugin = plugin
            self.id_ = id_
            self.connection_file = connection_file
            self.hostname = hostname
            self.menu_actions = menu_actions
            self.slave = slave
            self.external_kernel = external_kernel
            self.given_name = given_name
            self.show_elapsed_time = show_elapsed_time
            self.reset_warning = reset_warning
            self.ask_before_restart = kwargs["ask_before_restart"] if "ask_before_restart" in kwargs else None
            self.ask_before_closing = kwargs["ask_before_closing"] if "ask_before_closing" in kwargs else None

            # --- Other attrs
            if spyder.version_info > (4,) and "options_button" in kwargs:
                self.options_button = kwargs["options_button"]
            else:
                self.options_button = None
            self.stop_button = None
            self.reset_button = None
            self.stop_icon = ima.icon('stop')
            self.history = []
            self.allow_rename = True
            self.stderr_dir = None
            self.is_error_shown = False
            self.restart_thread = None

            if "css_path" in kwargs:
                if kwargs["css_path"] is None:
                    self.css_path = CSS_PATH
                else:
                    self.css_path = kwargs["css_path"]

            # --- Widgets
            self.shellwidget = MxShellWidget(
                config=config_options,
                ipyclient=self,
                additional_options=additional_options,
                interpreter_versions=interpreter_versions,
                external_kernel=external_kernel,
                local_kernel=True
            )

            self.infowidget = plugin.infowidget
            self.blank_page = self._create_blank_page()

            self.loading_page = self._create_loading_page()
            # To keep a reference to the page to be displayed
            # in infowidget
            self.info_page = None
            if spyder.version_info < (4, 1):
                self._show_loading_page()
            else:
                self._before_prompt_is_ready()

            # Elapsed time
            self.time_label = None
            self.t0 = time.monotonic()

            self.timer = QTimer(self)
            self.show_time_action = create_action(self, _("Show elapsed time"),
                                                 toggled=self.set_elapsed_time_visible)
            # --- Layout
            self.layout = QVBoxLayout()
            toolbar_buttons = self.get_toolbar_buttons()

            hlayout = QHBoxLayout()
            hlayout.addWidget(self.create_time_label())
            hlayout.addStretch(0)
            for button in toolbar_buttons:
                hlayout.addWidget(button)

            self.layout.addLayout(hlayout)
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.addWidget(self.shellwidget)
            self.layout.addWidget(self.infowidget)
            self.setLayout(self.layout)

            # --- Exit function
            self.exit_callback = lambda: plugin.close_client(client=self)

            # --- Dialog manager
            self.dialog_manager = DialogManager()

            # Show timer
            self.update_time_label_visibility()

            # Poll for stderr changes
            if spyder.version_info > (5,):
                self.stderr_mtime = 0
                self.stderr_timer = QTimer(self)
                self.stderr_timer.timeout.connect(self.poll_stderr_file_change)
                self.stderr_timer.setInterval(1000)
                self.stderr_timer.start()

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
