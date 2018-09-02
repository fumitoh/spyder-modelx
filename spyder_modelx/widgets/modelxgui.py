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

# The source code is originated from:
# https://github.com/spyder-ide/spyder-plugin-cookiecutter
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
import ast

from modelx.qtgui.modeltree import ModelTreeModel
from qtpy.QtCore import QUrl, QTimer, Signal, Slot
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox,
                            QToolButton, QVBoxLayout, QWidget, QTreeView)
from qtpy.QtWidgets import QTextEdit
from spyder.widgets.ipythonconsole.client import ShellWidget
from spyder.widgets.ipythonconsole.client import ClientWidget
from spyder.widgets.mixins import SaveHistoryMixin
from spyder.widgets.browser import WebView
from spyder.utils import encoding
from spyder.utils import icon_manager as ima
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, DialogManager,
                                    MENU_SEPARATOR)
from spyder.py3compat import PY2, to_text_string

class ModelxWidget(QWidget):
    """modelx widget."""

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.setWindowTitle("modelx")

        self.treeview = QTreeView()

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.treeview)
        self.setLayout(layout)

    def process_remote_view(self, data):
        if data:
            model = self.treeview.model()
            if model:
                if model.modelid == data['id']:
                    if model.rootItem.itemData != data:
                        model.updateRoot(data)
                else:
                    self.treeview.setModel(ModelTreeModel(data))
            else:
                self.treeview.setModel(ModelTreeModel(data))
        else:
            self.treeview.setModel(None)


class ModelxTreeView(QTreeView):
    pass


class ModelxTreeModel():
    pass


class ModelxClientWidget(ClientWidget):
    """Custom client widget for modelx

    The only difference from ClientWidget is its
    shell member being ModelxShellWidget
    """

    def __init__(self, plugin, id_,
                 history_filename, config_options,
                 additional_options, interpreter_versions,
                 connection_file=None, hostname=None,
                 menu_actions=None, slave=False,
                 external_kernel=False, given_name="Modelx Console",
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
        self.shellwidget = ModelxShellWidget(
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
        self.shellwidget.set_modelxbrowser(plugin.widget)


class ModelxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    sig_modelx_view = Signal(object)

    def set_modelxbrowser(self, modelxbrowser):
        """Set namespace browser widget"""
        self.modelxbrowser = modelxbrowser
        self.configure_modelxbrowser()

    def configure_modelxbrowser(self):
        """Configure associated namespace browser widget"""
        # Update namespace view
        self.sig_modelx_view.connect(lambda data:
            self.modelxbrowser.process_remote_view(data))
        

    # ---- Override NamespaceBrowserWidget ---
    def refresh_namespacebrowser(self):
        """Refresh namespace browser"""

        super(ModelxShellWidget, self).refresh_namespacebrowser()

        if self.namespacebrowser:
            self.silent_exec_method(
                'get_ipython().kernel.mx_get_models()')


    def handle_exec_method(self, msg):
        """
        Handle data returned by silent executions of kernel methods

        This is based on the _handle_exec_callback of RichJupyterWidget.
        Therefore this is licensed BSD.
        """
        user_exp = msg['content'].get('user_expressions')
        if not user_exp:
            return
        for expression in user_exp:
            if expression in self._kernel_methods:
                # Process kernel reply
                method = self._kernel_methods[expression]
                reply = user_exp[expression]
                data = reply.get('data')
                if 'mx_get_models' in method:
                    if data is not None and 'text/plain' in data:
                        literal = ast.literal_eval(data['text/plain'])
                        view = ast.literal_eval(literal)
                    else:
                        view = None
                    self.sig_modelx_view.emit(view)
                elif 'get_namespace_view' in method:
                    if data is not None and 'text/plain' in data:
                        literal = ast.literal_eval(data['text/plain'])
                        view = ast.literal_eval(literal)
                    else:
                        view = None
                    self.sig_namespace_view.emit(view)
                elif 'get_var_properties' in method:
                    if data is not None and 'text/plain' in data:
                        literal = ast.literal_eval(data['text/plain'])
                        properties = ast.literal_eval(literal)
                    else:
                        properties = None
                    self.sig_var_properties.emit(properties)
                elif 'get_cwd' in method:
                    if data is not None and 'text/plain' in data:
                        self._cwd = ast.literal_eval(data['text/plain'])
                        if PY2:
                            self._cwd = encoding.to_unicode_from_fs(self._cwd)
                    else:
                        self._cwd = ''
                    self.sig_change_cwd.emit(self._cwd)
                elif 'get_syspath' in method:
                    if data is not None and 'text/plain' in data:
                        syspath = ast.literal_eval(data['text/plain'])
                    else:
                        syspath = None
                    self.sig_show_syspath.emit(syspath)
                elif 'get_env' in method:
                    if data is not None and 'text/plain' in data:
                        env = ast.literal_eval(data['text/plain'])
                    else:
                        env = None
                    self.sig_show_env.emit(env)
                elif 'getattr' in method:
                    if data is not None and 'text/plain' in data:
                        is_spyder_kernel = data['text/plain']
                        if 'SpyderKernel' in is_spyder_kernel:
                            self.sig_is_spykernel.emit(self)
                else:
                    if data is not None and 'text/plain' in data:
                        self._kernel_reply = ast.literal_eval(data['text/plain'])
                    else:
                        self._kernel_reply = None
                    self.sig_got_reply.emit()

                # Remove method after being processed
                self._kernel_methods.pop(expression)