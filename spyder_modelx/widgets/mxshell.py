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
import ast
import uuid
import time
from collections import namedtuple
import cloudpickle
from qtpy.QtCore import Signal, Slot, Qt, QEventLoop
from qtpy.QtWidgets import QMessageBox
# from spyder.widgets.reporterror import SpyderErrorDialog

import spyder
from spyder.config.base import _, debug_print
if spyder.version_info < (4,):
    from spyder.widgets.ipythonconsole.client import ShellWidget
else:
    from spyder.plugins.ipythonconsole.widgets.client import ShellWidget
from spyder.utils import encoding
from spyder.py3compat import PY2, to_text_string

from spyder_modelx.utility.tupleencoder import TupleEncoder, hinted_tuple_hook
from spyder_modelx.utility.formula import (
    is_funcdef, is_lambda, replace_funcname, get_funcname)

if spyder.version_info > (4,):
    from spyder.plugins.ipythonconsole.widgets.namespacebrowser import (
        CALL_KERNEL_TIMEOUT
    )


def _quote_string(arg):
    if arg:
        return "'%s'" % arg
    else:
        return ""


class MxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    sig_mxexplorer = Signal(object)
    sig_mxmodellist = Signal()
    sig_mxdataview_eval = Signal(object)
    sig_mxdataview_getval = Signal()  # Spyder 3 only
    sig_mxcodelist = Signal(object)
    sig_mxanalyzer = Signal(str, object)
    sig_mxanalyzer_status = Signal(str, bool, str)
    sig_mxanalyzer_precedents = Signal()
    sig_mxanalyzer_succs = Signal()
    sig_mxanalyzer_getval = Signal()   # Spyder 3 only
    sig_mxupdated = Signal()
    sig_mxproperty = Signal(object)
    sig_mxgetattrdict = Signal()     # Spyder 3 only
    sig_mxgetvalueinfo = Signal(object)     # Spyder 3 only

    mx_msgtypes = ['mxupdated',
                   'dataview',
                   'dataview_getval',   # Spyder 3 only
                   'codelist',
                   'explorer',
                   'modellist',
                   'analyze_precedents_setnode',
                   'analyze_succs_setnode',
                   'analyze_precedents',
                   'analyze_succs',
                   'analyze_getval',    # Spyder 3 only
                   'property',
                   'get_attrdict',      # Spyder 3 only
                   'get_value_info'     # Spyder 3 only
                   ]

    mx_nondata_msgs = ['mxupdated']

    _mx_value = None
    _MxRequest = namedtuple("_MxRequest",
                            ["msgtype", "code", "local_uuid", "usrexp"])

    def __init__(self, *args, **kw):

        self._mx_exec = {}
        super(MxShellWidget, self).__init__(*args, **kw)

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
        )   # TODO: Why wrap in lambdas?

    # ---- modelx data view ----
    def set_mxdataview(self, mxdataviewer):
        """Set modelx dataview widget"""
        # self.mxdataview = mxdataview
        # self.mxexprbox = mxexprbox
        self.mxdataviewer = mxdataviewer
        self.configure_mxdataview()

    def configure_mxdataview(self):
        """Configure mx data view widget"""
        # self.sig_mxdataview_eval.connect(
        #     lambda data: self.mxdataview.process_remote_view(data))

        # self.mxexprbox.editingFinished.connect(
        #     self.update_mxdataview)

        self.sig_mxdataview_eval.connect(self.mxdataviewer.update_value)
        if spyder.version_info > (5,):
            pass
        else:
            self.sig_mxproperty.connect(self.mxdataviewer.update_object)

    def get_obj_value(self, msgtype: str, obj: str, args: str,
                      calc: bool=False):

        # jsonargs = TupleEncoder(ensure_ascii=True).encode(args)

        if spyder.version_info > (4,):
            result = self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_value(
                msgtype, obj, args, calc
            )
            return result
        else:
            code = (
                    "get_ipython().kernel.mx_get_value('%s', '%s', '%s', %s)"
                    % (msgtype, obj, args, calc)
            )

            # The code below is replaced with silent_exec_method

            # if self._reading:
            #     method = self.kernel_client.input
            #     code = u'!' + code
            # else:
            #     method = self.silent_execute

            # Wait until the kernel returns the value
            if msgtype == 'dataview_getval':
                sig = self.sig_mxdataview_getval
            elif msgtype == 'analyze_getval':
                sig = self.sig_mxanalyzer_getval
            else:
                raise RuntimeError('must not happen')

            return self._mx_wait_reply(code, sig)

    def update_mxdataview(self, is_obj, obj=None, args=None, expr=None, calc=False):
        """Update dataview"""
        # expr = self.mxdataviewer.exprbox.get_expr()
        if is_obj:
            return self.get_obj_value('dataview_getval', obj, args, calc)
        else:
            if expr:
                method = "get_ipython().kernel.mx_get_evalresult('dataview', %s)" % expr
                self.mx_silent_exec_method(method, msgtype='dataview')

            return None

    # ---- modelx data list ----
    def set_mxdatalist(self, datalist):
        """Set modelx formula list"""
        self.mxdatalist = datalist
        self.sig_mxgetvalueinfo.connect(
            lambda data: self.mxdatalist.process_remote_view(data))

    def update_datalist(self):
        """Update codelist"""
        model = self.mxmodelselector.get_selected_model()

        if not model:
            return

        if spyder.version_info > (4,):
            result = self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_value_info(model)
            self.mxdatalist.process_remote_view(result)
        else:
            code = "get_ipython().kernel.mx_get_value_info('%s')" % model
            self.mx_silent_exec_method(code, msgtype='get_value_info')

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
        self.mx_silent_exec_method(method, msgtype='codelist')

    # ---- modelx analyzer ----
    def set_mxanalyzer(self, analyzer):
        """Set modelx dataview widget"""
        self.mxanalyzer = analyzer
        self.configure_mxanalyzer()

    def configure_mxanalyzer(self):
        """Configure mx data view widget"""
        self.sig_mxanalyzer.connect(self.mxanalyzer.update_node)
        self.sig_mxanalyzer_status.connect(self.mxanalyzer.update_status)

        for adjacency in ['precedents', 'succs']:

            tab = self.mxanalyzer.tabs[adjacency]

            for box in [tab.exprobjbox, tab.exprargbox, tab.argbox]:
                # adjacenty is a free varible
                # cannot pass it to update_mxanalyzer in lambda
                if adjacency == 'precedents':
                    box.editingFinished.connect(
                        lambda: self.update_mxanalyzer('precedents')
                    )
                elif adjacency == 'succs':
                    box.editingFinished.connect(
                        lambda: self.update_mxanalyzer('succs')
                    )
                else:
                    RuntimeError('must not happen')

    def get_attrdict(self, fullname=None, attrs=None, recursive=False):

        if spyder.version_info > (4,):
            return self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_attrdict(
                fullname=fullname, attrs=attrs, recursive=recursive
            )
        else:
            param = "'%s', ['formula', '_evalrepr', 'allow_none', 'parameters']" % fullname
            code = "get_ipython().kernel.mx_get_attrdict(" + param + ")"

            return self._mx_wait_reply(
                None,
                self.sig_mxgetattrdict,
                code
            )


    def update_mxanalyzer(self, adjacency, update_attrdict=True):

        tab = self.mxanalyzer.tabs[adjacency]

        if tab.object_radio.isChecked():
            if not tab.attrdict:
                return
            if update_attrdict:
                tab.attrdict = self.get_attrdict(
                    fullname=tab.attrdict['fullname'],
                    attrs=['formula', '_evalrepr', 'allow_none', 'parameters'],
                    recursive=False
                )
            if not tab.attrdict:
                tab.clear_obj()
                return
            tab.set_argbox()
            self._update_mxanalyzer_obj(adjacency, update_attrdict)
        elif tab.expr_radio.isChecked():
            self._update_mxanalyzer_expr(adjacency)

    def _update_mxanalyzer_obj(self, adjacency, update_attrdict):

        tab = self.mxanalyzer.tabs[adjacency]
        msgtype = "analyze_" + adjacency + "_setnode"
        obj = tab.attrdict['fullname']
        argtxt = tab.argbox.get_expr()
        args = "(" + argtxt + ("," if argtxt else "") + ")"

        if spyder.version_info > (4,):

            try:
                result = self.call_kernel(
                    interrupt=True,
                    blocking=True,
                    timeout=CALL_KERNEL_TIMEOUT).mx_get_node(
                    msgtype, obj, args
                )
                self.mxanalyzer.update_status(adjacency, True)
                self.sig_mxanalyzer.emit(adjacency, result)
            except Exception as e:
                msg = e.__class__.__name__ + ": " + str(e)
                self.mxanalyzer.update_status(adjacency, False, msg)

        else:
            str1 = "get_ipython().kernel.mx_get_node"
            str2 = "('%s', '%s', '%s')" % (msgtype, obj, args)
            #Issue: need to double quote string args

            self.mx_silent_exec_method(str1+str2, msgtype=msgtype)


    def _update_mxanalyzer_expr(self, adjacency):
        """Update dataview"""

        tab = self.mxanalyzer.tabs[adjacency]
        objexpr = tab.exprobjbox.get_expr()
        argexpr = tab.exprargbox.get_expr()

        # Invalid expression
        if objexpr is None or argexpr is None:
            return

        if objexpr:
            expr = objexpr + ".node(" + argexpr + ")"
            msgtype = "analyze_" + adjacency + "_setnode"
            msgtype_quotes = "\"" + msgtype + "\""

            str1 = "get_ipython().kernel.mx_get_evalresult"
            str2 = "(%s, %s." % (msgtype_quotes, expr)
            str3 = "_get_attrdict(recursive=False, extattrs=['formula']))"

            self.mx_silent_exec_method(str1+str2+str3, msgtype=msgtype)

    def update_mxanalyzer_all(self):
        for adj in ['precedents', 'succs']:
            self.update_mxanalyzer(adj)

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
            if adjacency == 'precedents':
                sig = self.sig_mxanalyzer_precedents
            elif adjacency == 'succs':
                sig = self.sig_mxanalyzer_succs
            else:
                raise RuntimeError("must not happen")

            return self._mx_wait_reply(code, sig)

    # ---- modelx property widget ----
    def set_mxproperty(self, mxproperty):
        """Set modelx dataview widget"""
        mxproperty.shell = self
        self.mxproperty = mxproperty
        self.configure_mxproperty()

    def configure_mxproperty(self):
        """Configure mx data view widget"""
        self.sig_mxproperty.connect(
            lambda data: self.mxproperty.process_remote_view(data))

    def update_mxproperty(self, objname):
        param = "'property', '%s', ['formula', '_evalrepr', 'allow_none', 'parameters']" % objname
        code = "get_ipython().kernel.mx_get_object(" + param + ")"
        val = self.mx_silent_exec_method(code, msgtype="property")
        return val

    def reload_mxproperty(self):
        objid = self.mxproperty.objectId
        if objid:
            return self.update_mxproperty(objid)

    def _mx_wait_reply(self, usrexp, sig, code=''):

        wait_loop = QEventLoop()
        sig.connect(wait_loop.quit)
        self.mx_silent_exec_method(usrexp, code)
        wait_loop.exec_()

        # Remove loop connection and loop
        sig.disconnect(wait_loop.quit)
        wait_loop = None

        if spyder.version_info < (4,):
            # Handle exceptions
            if sig not in self.mx_nondata_msgs:
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

        param = "'explorer', %s, ['_is_derived', '__len__', '_evalrepr'], recursive=True" % arg

        self.mx_silent_exec_method(
            "get_ipython().kernel.mx_get_object(" + param + ")",
            msgtype='explorer'
        )
        # self.update_mxdataview()    # TODO: Redundant?

    def new_model(self, name=None, define_var=False, varname=''):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_new_model(
                name, define_var, varname)
        else:
            # name = _quote_string(name)
            # varname = _quote_string(varname)
            if define_var:
                define_var = "True"
            else:
                define_var = "False"

            code = "get_ipython().kernel.mx_new_model('%s', %s, '%s')" % (
                name, define_var, varname)
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def read_model(self, modelpath, name, define_var, varname):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_read_model(
                modelpath, name, define_var, varname)
        else:
            if define_var:
                define_var = "True"
            else:
                define_var = "False"

            params = "'%s', '%s', %s, '%s'" % (
                modelpath, name, define_var, varname
            )
            code = "get_ipython().kernel.mx_read_model(" + params + ")"
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def new_space(self, model, parent, name, bases, define_var, varname):

        paramlist = "'%s', '%s', '%s', '%s', %s, '%s'" % (
            model, parent, name, bases, str(define_var), varname
        )
        code = "get_ipython().kernel.mx_new_space(" + paramlist + ")"
        self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def new_cells(self, model, parent, name, formula, define_var, varname):

        if formula:

            try:
                if is_funcdef(formula):
                    if not name:
                        name = get_funcname(formula)
                    formula = replace_funcname(formula, "__mx_temp")
                elif is_lambda(formula):
                    formula = "__mx_temp = " + formula.lstrip()
                else:
                    QMessageBox.critical(self,
                                         title="Error",
                                         text="Invalid formula")

            except SystemError:
                QMessageBox.critical(self, title="Error", text="Syntax error")
                return

        paramlist = "'%s', '%s', '%s', %s, '%s'" % (
            model, parent, name, str(define_var), varname
        )
        code = "get_ipython().kernel.mx_new_cells(" + paramlist + ")"
        code = formula + "\n" + code

        self._mx_wait_reply(
            None,
            self.sig_mxupdated,
            code
        )
        self.refresh_namespacebrowser()

    def set_formula(self, fullname, formula):

        if is_funcdef(formula):
            formula = replace_funcname(formula, "__mx_temp")
        elif is_lambda(formula):
            formula = "__mx_temp = " + formula.lstrip()

        code = "get_ipython().kernel.mx_set_formula('%s')" % fullname
        code = formula + "\n" + code

        self._mx_wait_reply(
            None,
            self.sig_mxupdated,
            code
        )
        self.refresh_namespacebrowser()

    def del_object(self, parent, name):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_del_object(
                parent, name)
        else:
            params = "'%s', '%s'" % (
                parent, name
            )
            code = "get_ipython().kernel.mx_del_object(" + params + ")"
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def del_model(self, name):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_del_model(
                name)
        else:
            code = "get_ipython().kernel.mx_del_model('%s')" % name
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def write_model(self, model, modelpath, backup, zipmodel):

        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_write_model(
                model, modelpath, backup, zipmodel)
        else:
            param = "'%s', '%s', %s, %s" % (model, modelpath, str(backup), str(zipmodel))
            code = "get_ipython().kernel.mx_write_model(" + param + ")"
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    def import_names(self,
                     fullname,
                     import_selected,
                     import_children,
                     replace_existing
    ):
        if spyder.version_info > (4,):
            self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_import_names(
                fullname, import_selected, import_children, replace_existing)
        else:
            param = "'%s', %s, %s, %s" % (
                fullname,
                str(import_selected),
                str(import_children),
                str(replace_existing)
            )
            code = "get_ipython().kernel.mx_import_names(" + param + ")"
            self._mx_wait_reply(
                None,
                self.sig_mxupdated,
                code
            )
        self.refresh_namespacebrowser()

    if spyder.version_info < (4,):
        # ---- Override NamespaceBrowserWidget ---
        def refresh_namespacebrowser(self):
            """Refresh namespace browser"""

            super(MxShellWidget, self).refresh_namespacebrowser()
            if self.kernel_client is None:
                return
            if self.namespacebrowser:
                mlist = self.get_modellist()
                name = self.mxmodelselector.get_selected_model(mlist)
                self.update_modeltree(name)
                self.reload_mxproperty()
                self.update_datalist()
                self.update_mxanalyzer_all()
    else:
        # ---- Override NamespaceBrowserWidget ---
        def refresh_namespacebrowser(self, interrupt=False):
            """Refresh namespace browser"""

            super(MxShellWidget, self).refresh_namespacebrowser(
                interrupt=interrupt
            )
            if self.kernel_client is None:
                return
            elif not hasattr(self.kernel_client, 'comm_channel'):
                return
            elif self.kernel_client.comm_channel is None:
                return
            if self.namespacebrowser and self.spyder_kernel_comm.is_open():
                mlist = self.get_modellist()
                name = self.mxmodelselector.get_selected_model(mlist)
                self.update_modeltree(name)
                self.reload_mxproperty()
                self.update_datalist()
                self.update_mxanalyzer_all()

    # ---- Private API (defined by us) ------------------------------
    def mx_silent_exec_method(self, usrexp=None, code='', msgtype=None):
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
            local_uuid = ""
            usrexp = {}

        if self.kernel_client is None:
            return

        msg_id = self.kernel_client.execute(
            code,
            silent=True,
            user_expressions=usrexp
        )
        self._mx_exec[msg_id] = self._MxRequest(
            msgtype=msgtype, code=code, local_uuid=local_uuid,
            usrexp=usrexp[local_uuid] if usrexp else usrexp)

        if 'hidden' in self._ExecutionRequest._fields:  # depends on qtconsole version
            self._request_info['execute'][msg_id] = self._ExecutionRequest(
                msg_id,
                'mx_silent_exec_method',
                False
            )
        else:
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
        if hasattr(self, '_hidden'):    # depends on qtconsole version
            cond = info and info.kind == 'mx_silent_exec_method' and not self._hidden
        else:
            cond = info and info.kind == 'mx_silent_exec_method'

        if cond:
            msgtype = self._mx_exec[msg_id].msgtype

            if msgtype and msgtype[:len("analyze_")] == "analyze_":
                local_uuid = self._mx_exec[msg_id].local_uuid
                result = msg['content']['user_expressions'][local_uuid]
                adjacency = msgtype.split("_")[1]
                if result['status'] == "error":
                    errmsg = result['ename'] + ": " + result['evalue']
                    self.sig_mxanalyzer_status.emit(adjacency, False, errmsg)
                else:
                    self.sig_mxanalyzer_status.emit(adjacency, True, "")

            self._mx_exec.pop(msg_id)
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

            if msgtype == 'mxupdated':
                self.sig_mxupdated.emit()
            elif msgtype == 'dataview':
                self.sig_mxdataview_eval.emit(value)
            elif msgtype == 'dataview_getval':
                if spyder.version_info > (4,):
                    raise AssertionError("must not happen")
                self._mx_value = value
                self.sig_mxdataview_getval.emit()
            elif msgtype == 'codelist':
                self.sig_mxcodelist.emit(value)
            elif msgtype == 'explorer':
                self.sig_mxexplorer.emit(value)
            elif msgtype == 'modellist':
                if spyder.version_info > (4,):
                    raise AssertionError("must not happen")
                self._mx_value = value
                self.sig_mxmodellist.emit()
            elif msgtype == 'analyze_precedents_setnode':
                self.sig_mxanalyzer.emit('precedents', value)
            elif msgtype == 'analyze_succs_setnode':
                self.sig_mxanalyzer.emit('succs', value)
            elif msgtype == 'analyze_precedents':
                if spyder.version_info > (4,):
                    raise AssertionError("must not happen")
                self._mx_value = value
                self.sig_mxanalyzer_precedents.emit()
            elif msgtype == 'analyze_succs':
                if spyder.version_info > (4,):
                    raise AssertionError("must not happen")
                self._mx_value = value
                self.sig_mxanalyzer_succs.emit()
            elif msgtype == 'analyze_getval':
                if spyder.version_info > (4,):
                    raise AssertionError("must not happen")
                self._mx_value = value
                self.sig_mxanalyzer_getval.emit()
            elif msgtype == 'property':
                self.sig_mxproperty.emit(value)
            elif msgtype == 'get_attrdict':
                self._mx_value = value
                self.sig_mxgetattrdict.emit()
            elif msgtype == 'get_value_info':
                self.sig_mxgetvalueinfo.emit(value)

            # Copied _handle_execute_reply
            if info and info.kind == 'silent_exec_method' and not self._hidden:
                self._request_info['execute'].pop(msg_id)
            return

        else:
            debug_print("No such modelx message type: %s" % msgtype)

