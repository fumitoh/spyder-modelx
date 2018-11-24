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

import cloudpickle
from qtpy.QtCore import Signal, Slot, Qt

from spyder.config.base import _, debug_print
from spyder.widgets.ipythonconsole.client import ShellWidget
from spyder.utils import encoding
from spyder.py3compat import PY2


class MxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    sig_mxexplorer = Signal(object)
    sig_mxdataview = Signal(object)
    sig_mxcodelist = Signal(object)

    # ---- modelx browser ----
    def set_mxexplorer(self, mxexplorer):
        """Set namespace browser widget"""
        self.mxexplorer = mxexplorer
        mxexplorer.treeview.shell = self
        self.configure_mxexplorer()

    def configure_mxexplorer(self):
        """Configure associated namespace browser widget"""
        # Update namespace view
        self.sig_mxexplorer.connect(lambda data:
                                    self.mxexplorer.process_remote_view(data))

    # ---- modelx data view ----
    def set_mxdataview(self, mxdataview, mxexprbox):
        """Set modelx dataview widget"""
        self.mxdataview = mxdataview
        self.mxexprbox = mxexprbox
        self.configure_mxdataview()

    def configure_mxdataview(self):
        """Configure mx data view widget"""
        self.sig_mxdataview.connect(
            lambda data: self.mxdataview.process_remote_view(data))

        self.mxexprbox.editingFinished.connect(
            self.update_mxdataview)

    def update_mxdataview(self):
        """Update dataview"""
        expr = self.mxexprbox.get_expr()
        method = "get_ipython().kernel.mx_get_evalresult('data', %s)" % expr
        self.silent_exec_method(method)

    # ---- modelx code list ----
    def set_mxcodelist(self, codelist):
        """Set modelx formula list"""
        self.mxcodelist = codelist
        self.sig_mxcodelist.connect(lambda data:
                                    self.mxcodelist.process_remote_view(data))

    def update_codelist(self, objname):
        """Update codelist"""
        objname = '"' + objname + '.cells' + '"'
        method = 'get_ipython().kernel.mx_get_codelist(%s)' % objname
        self.silent_exec_method(method)

    # ---- Override NamespaceBrowserWidget ---
    def refresh_namespacebrowser(self):
        """Refresh namespace browser"""

        super(MxShellWidget, self).refresh_namespacebrowser()

        if self.namespacebrowser:
            self.silent_exec_method(
                'get_ipython().kernel.mx_get_models()')
            self.update_mxdataview()
            # self.silent_exec_method(
            #     'get_ipython().kernel.mx_get_evalresult(mx.cur_space().frame)')

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
                    self.sig_mxexplorer.emit(view)
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
                        self._kernel_reply = ast.literal_eval \
                            (data['text/plain'])
                    else:
                        self._kernel_reply = None
                    self.sig_got_reply.emit()

                # Remove method after being processed
                self._kernel_methods.pop(expression)

    # ---- Private API (defined by us) ------------------------------
    def _handle_modelx_msg(self, msg):
        """
        Handle internal spyder messages
        """
        mx_msgtype = msg['content'].get('mx_msgtype')
        if mx_msgtype == 'data' or mx_msgtype == 'codelist':
            # Deserialize data
            try:
                if PY2:
                    value = cloudpickle.loads(msg['buffers'][0])
                else:
                    value = cloudpickle.loads(bytes(msg['buffers'][0]))
            except Exception as msg:
                value = None

            if mx_msgtype == 'data':
                self.sig_mxdataview.emit(value)
            else:
                self.sig_mxcodelist.emit(value)
            return
        else:
            debug_print("No such modelx message type: %s" % mx_msgtype)
