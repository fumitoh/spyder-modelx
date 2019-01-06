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
import ast

import cloudpickle
from qtpy.QtCore import Signal, Slot, Qt, QEventLoop

from spyder.config.base import _, debug_print
from spyder.widgets.ipythonconsole.client import ShellWidget
from spyder.utils import encoding
from spyder.py3compat import PY2

from spyder_modelx.util import TupleEncoder, hinted_tuple_hook

class MxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    sig_mxexplorer = Signal(object)
    sig_mxdataview = Signal(object)
    sig_mxcodelist = Signal(object)
    sig_mxanalyzer = Signal(object)

    mx_msgtypes = ['dataview',
                   'codelist',
                   'explorer',
                   'analyzer',
                   'analyze_preds',
                   'analyze_succs']

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
        method = "get_ipython().kernel.mx_get_evalresult('dataview', %s)" % expr
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

    # ---- modelx analyzer ----
    def set_mxanalyzer(self, analyzer, objbox, argbox):
        """Set modelx dataview widget"""
        self.mxanalyzer = analyzer
        self.mxobjbox = objbox
        self.mxargbox = argbox
        self.configure_mxanalyzer()

    def configure_mxanalyzer(self):
        """Configure mx data view widget"""
        self.sig_mxanalyzer.connect(
            lambda data: self.mxanalyzer.tree.process_remote_view(data))

        self.mxobjbox.editingFinished.connect(
            self.update_mxanalyzer)

        self.mxargbox.editingFinished.connect(
            self.update_mxanalyzer)

    def update_mxanalyzer(self):
        """Update dataview"""
        objexpr = self.mxobjbox.get_expr()
        argexpr = self.mxargbox.get_expr()

        # Invalid expression
        if objexpr is None or argexpr is None:
            return

        if objexpr:
            expr = objexpr + ".node(" + argexpr + ")"
            method = "get_ipython().kernel." + \
                     "mx_get_evalresult('analyzer', %s._baseattrs)" % expr
            self.silent_exec_method(method)

    def get_adjacent(self, obj: str, args: tuple, adjacency: str):

        jsonargs = TupleEncoder(ensure_ascii=True).encode(args)

        code = "get_ipython().kernel." + \
               "mx_get_adjacent('analyze_preds', '%s', '%s', '%s')" \
               % (obj, jsonargs, adjacency)

        if self._reading:
            method = self.kernel_client.input
            code = u'!' + code
        else:
            method = self.silent_execute

        # Wait until the kernel returns the value
        wait_loop = QEventLoop()
        self.sig_got_reply.connect(wait_loop.quit)
        method(code)
        wait_loop.exec_()

        # Remove loop connection and loop
        self.sig_got_reply.disconnect(wait_loop.quit)
        wait_loop = None

        # Handle exceptions
        if self._kernel_value is None:
            if self._kernel_reply:
                msg = self._kernel_reply[:]
                self._kernel_reply = None
                raise ValueError(msg)

        return self._kernel_value

    # ---- Override NamespaceBrowserWidget ---
    def refresh_namespacebrowser(self):
        """Refresh namespace browser"""

        super(MxShellWidget, self).refresh_namespacebrowser()

        if self.namespacebrowser:
            self.silent_exec_method(
                "get_ipython().kernel.mx_get_object('explorer')")
            self.update_mxdataview()

    # ---- Private API (defined by us) ------------------------------
    def _handle_modelx_msg(self, msg):
        """
        Handle internal spyder messages
        """
        msg_id = msg['parent_header']['msg_id']
        info = self._request_info['execute'].get(msg_id)

        msgtype = msg['content'].get('mx_msgtype')

        if msgtype in self.mx_msgtypes:
            # Deserialize data
            try:
                if PY2:
                    value = cloudpickle.loads(msg['buffers'][0])
                else:
                    value = cloudpickle.loads(bytes(msg['buffers'][0]))
            except Exception as msg:
                value = None

            if msgtype == 'dataview':
                self.sig_mxdataview.emit(value)
            elif msgtype == 'codelist':
                self.sig_mxcodelist.emit(value)
            elif msgtype == 'explorer':
                self.sig_mxexplorer.emit(value)
            elif msgtype == 'analyzer':
                self.sig_mxanalyzer.emit(value)
            elif msgtype == 'analyze_preds':
                self._kernel_value = value
                self.sig_got_reply.emit()

            # Copied _handle_execute_reply
            if info and info.kind == 'silent_exec_method' and not self._hidden:
                self._request_info['execute'].pop(msg_id)
            return

        else:
            debug_print("No such modelx message type: %s" % msgtype)

