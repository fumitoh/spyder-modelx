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

"""modelx Widget."""
import ast
import uuid
import time
import cloudpickle
from qtpy.QtCore import Signal, Slot, Qt, QEventLoop
from qtpy.QtWidgets import QMessageBox
from spyder.widgets.reporterror import SpyderErrorDialog

import spyder
from spyder.config.base import _, debug_print
if spyder.version_info < (4,):
    from spyder.widgets.ipythonconsole.client import ShellWidget
else:
    from spyder.plugins.ipythonconsole.widgets.client import ShellWidget
from spyder.utils import encoding
from spyder.py3compat import PY2, to_text_string

from spyder_modelx.util import TupleEncoder, hinted_tuple_hook

if spyder.version_info > (4,):
    from spyder.plugins.ipythonconsole.widgets.namespacebrowser import (
        CALL_KERNEL_TIMEOUT
    )

class MxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    sig_mxexplorer = Signal(object)
    sig_mxmodellist = Signal()
    sig_mxdataview = Signal(object)
    sig_mxcodelist = Signal(object)
    sig_mxanalyzer = Signal(str, object)
    sig_mxanalyze_preds = Signal()
    sig_mxanalyze_succs = Signal()

    mx_msgtypes = ['dataview',
                   'codelist',
                   'explorer',
                   'modellist',
                   'analyze_preds_setnode',
                   'analyze_succs_setnode',
                   'analyze_preds',
                   'analyze_succs']

    _mx_value = None

    # ---- modelx browser ----
    def set_mxexplorer(self, mxexplorer, mxmodelselector):
        """Set namespace browser widget"""
        self.mxexplorer = mxexplorer
        self.mxmodelselector = mxmodelselector
        mxexplorer.treeview.shell = self
        self.configure_mxexplorer()

    def configure_mxexplorer(self):
        """Configure associated namespace browser widget"""
        # Update namespace view

        self.sig_mxexplorer.connect(
            lambda data: self.mxexplorer.process_remote_view(data))
        self.mxmodelselector.activated.connect(
            lambda : self.update_modeltree(
                self.mxmodelselector.get_selected_model()
            )
        )

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
        if expr:
            method = "get_ipython().kernel.mx_get_evalresult('dataview', %s)" % expr
            self.mx_silent_exec_method(method)

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
        self.mx_silent_exec_method(method)

    # ---- modelx analyzer ----
    def set_mxanalyzer(self, analyzer):
        """Set modelx dataview widget"""
        self.mxanalyzer = analyzer
        self.configure_mxanalyzer()

    def configure_mxanalyzer(self):
        """Configure mx data view widget"""
        self.sig_mxanalyzer.connect(self.mxanalyzer.update_node)

        tab = self.mxanalyzer.tabs['preds']

        tab.objbox.editingFinished.connect(
            lambda: self.update_mxanalyzer('preds')
        )
        tab.argbox.editingFinished.connect(
            lambda: self.update_mxanalyzer('preds')
        )

        tab = self.mxanalyzer.tabs['succs']

        tab.objbox.editingFinished.connect(
            lambda: self.update_mxanalyzer('succs')
        )
        tab.argbox.editingFinished.connect(
            lambda: self.update_mxanalyzer('succs')
        )

    def update_mxanalyzer(self, adjacency):
        """Update dataview"""

        tab = self.mxanalyzer.tabs[adjacency]
        objexpr = tab.objbox.get_expr()
        argexpr = tab.argbox.get_expr()

        # Invalid expression
        if objexpr is None or argexpr is None:
            return

        if objexpr:
            expr = objexpr + ".node(" + argexpr + ")"
            msgtype = "\"analyze_" + adjacency + "_setnode\""
            method = (
                "get_ipython().kernel.mx_get_evalresult(%s, %s._baseattrs)"
                % (msgtype, expr)
            )
            self.mx_silent_exec_method(method)

    def get_adjacent(self, obj: str, args: tuple, adjacency: str):

        jsonargs = TupleEncoder(ensure_ascii=True).encode(args)
        msgtype = "analyze_" + adjacency

        if spyder.version_info > (4,):
            result = self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_adjacent(
                msgtype, obj, jsonargs, adjacency
            )
            return result
        else:
            code = (
                "get_ipython().kernel.mx_get_adjacent('%s', '%s', '%s', '%s')"
                % (msgtype, obj, jsonargs, adjacency)
            )

            # The code below is replaced with silent_exec_method

            # if self._reading:
            #     method = self.kernel_client.input
            #     code = u'!' + code
            # else:
            #     method = self.silent_execute

            # Wait until the kernel returns the value
            if adjacency == 'preds':
                sig = self.sig_mxanalyze_preds
            elif adjacency == 'succs':
                sig = self.sig_mxanalyze_succs
            else:
                raise RuntimeError("must not happen")

            return self._mx_wait_reply(code, sig)

    def _mx_wait_reply(self, usrexp, sig, code=''):

        wait_loop = QEventLoop()
        sig.connect(wait_loop.quit)
        self.mx_silent_exec_method(usrexp, code)
        wait_loop.exec_()

        # Remove loop connection and loop
        sig.disconnect(wait_loop.quit)
        wait_loop = None

        # Handle exceptions
        if self._mx_value is None:
            if self._kernel_reply:
                msg = self._kernel_reply[:]
                self._kernel_reply = None
                raise ValueError(msg)

        result = self._mx_value
        self._mx_value = None

        return result

    def get_modellist(self):

        if spyder.version_info > (4,):
            mlist = self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_modellist()
        else:
            code = "get_ipython().kernel.mx_get_modellist()"
            mlist = self._mx_wait_reply(code, self.sig_mxmodellist)

        return mlist

    def update_modeltree(self, name):

        if name:
            arg = "'%s'" % name
        else:
            arg = "None"

        self.mx_silent_exec_method(
            "get_ipython().kernel.mx_get_object('explorer', %s)" % arg)
        self.update_mxdataview()

    def new_model(self, name=None):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_new_model(name)
        else:
            if name:
                name = "'%s'" % name
            else:
                name = ""

            code = "get_ipython().kernel.mx_new_model(%s)" % name
            self._mx_wait_reply(
                None,
                self.sig_mxmodellist,
                code
            )
        self.refresh_namespacebrowser()

    def new_space(self, model, parent, name, bases):

        code = "get_ipython().kernel.mx_new_space('%s', '%s', '%s', '%s')" % (
            model, parent, name, bases
        )
        self._mx_wait_reply(
                None,
                self.sig_mxmodellist,
                code
            )
        self.refresh_namespacebrowser()

    # ---- Override NamespaceBrowserWidget ---
    def refresh_namespacebrowser(self):
        """Refresh namespace browser"""

        if spyder.version_info < (4,):
            super(MxShellWidget, self).refresh_namespacebrowser()
        else:
            super(MxShellWidget, self).refresh_namespacebrowser(
                interrupt=True
            )
        if self.namespacebrowser:
            mlist = self.get_modellist()
            name = self.mxmodelselector.get_selected_model(mlist)
            self.update_modeltree(name)
            self.update_mxdataview()

    # ---- Private API (defined by us) ------------------------------
    def mx_silent_exec_method(self, usrexp=None, code=''):
        """Silently execute a kernel method and save its reply

        The methods passed here **don't** involve getting the value
        of a variable but instead replies that can be handled by
        ast.literal_eval.

        To get a value see `get_value`

        Parameters
        ----------
        code : string
            Code that contains the kernel method as part of its
            string

        See Also
        --------
        handle_exec_method : Method that deals with the reply

        Note
        ----
        This is based on the _silent_exec_callback method of
        RichJupyterWidget. Therefore this is licensed BSD
        """
        # Generate uuid, which would be used as an indication of whether or
        # not the unique request originated from here
        if usrexp:
            local_uuid = to_text_string(uuid.uuid1())
            usrexp = {local_uuid: usrexp}
        else:
            usrexp = {}

        if self.kernel_client is None:
            return

        msg_id = self.kernel_client.execute(
            code,
            silent=True,
            user_expressions=usrexp
        )
        self._request_info['execute'][msg_id] = self._ExecutionRequest(
            msg_id,
            'mx_silent_exec_method'
        )

    def _handle_execute_reply(self, msg):
        """
        Reimplemented to handle communications between Spyder
        and the kernel
        """
        msg_id = msg['parent_header']['msg_id']
        info = self._request_info['execute'].get(msg_id)
        # unset reading flag, because if execute finished, raw_input can't
        # still be pending.
        self._reading = False

        # Refresh namespacebrowser after the kernel starts running
        exec_count = msg['content'].get('execution_count', '')
        if exec_count == 0 and self._kernel_is_starting:
            if self.namespacebrowser is not None:
                self.set_namespace_view_settings()
                self.refresh_namespacebrowser()
            self._kernel_is_starting = False
            self.ipyclient.t0 = time.monotonic()

        # Handle silent execution of kernel methods
        if info and info.kind == 'mx_silent_exec_method' and not self._hidden:
            self._request_info['execute'].pop(msg_id)
        else:
            super(MxShellWidget, self)._handle_execute_reply(msg)

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
                self._kernel_reply = repr(msg)

            if msgtype == 'dataview':
                self.sig_mxdataview.emit(value)
            elif msgtype == 'codelist':
                self.sig_mxcodelist.emit(value)
            elif msgtype == 'explorer':
                self.sig_mxexplorer.emit(value)
            elif msgtype == 'modellist':
                self._mx_value = value
                self.sig_mxmodellist.emit()
            elif msgtype == 'analyze_preds_setnode':
                self.sig_mxanalyzer.emit('preds', value)
            elif msgtype == 'analyze_succs_setnode':
                self.sig_mxanalyzer.emit('succs', value)
            elif msgtype == 'analyze_preds':
                self._mx_value = value
                self.sig_mxanalyze_preds.emit()
            elif msgtype == 'analyze_succs':
                self._mx_value = value
                self.sig_mxanalyze_succs.emit()

            # Copied _handle_execute_reply
            if info and info.kind == 'silent_exec_method' and not self._hidden:
                self._request_info['execute'].pop(msg_id)
            return

        else:
            debug_print("No such modelx message type: %s" % msgtype)

