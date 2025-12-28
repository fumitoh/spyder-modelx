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
import logging
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
from spyder.plugins.ipythonconsole.widgets.client import ShellWidget
from spyder.utils import encoding

from spyder_modelx.utility.tupleencoder import TupleEncoder, hinted_tuple_hook
from spyder_modelx.utility.formula import (
    is_funcdef, is_lambda, replace_funcname, get_funcname)


from spyder.plugins.ipythonconsole.widgets.namespacebrowser import (
    CALL_KERNEL_TIMEOUT
)

logger = logging.getLogger(__name__)

def _quote_string(arg):
    if arg:
        return "'%s'" % arg
    else:
        return ""


class MxShellWidget(ShellWidget):
    """Custom shell widget for modelx"""

    def __init__(self, *args, **kw):

        self._mx_exec = {}
        super(MxShellWidget, self).__init__(*args, **kw)
        self.sig_kernel_state_arrived.connect(self.update_mx_widgets)

    @Slot(dict)
    def update_mx_widgets(self, kernel_state):
        """
        Modified from update_view in plugins/variableexplorer/widgets/namespacebrowser.py
        """
        # logger.debug("Updating mx widgets...")
        mlist = self.get_modellist()
        name = self.mxmodelselector.get_selected_model(mlist)
        self.update_modeltree(name)
        self.reload_mxproperty()
        self.update_datalist()
        self.update_mxanalyzer_all()

    # ---- modelx browser ----
    def set_mxexplorer(self, mxexplorer, mxmodelselector):
        """Set namespace browser widget"""
        self.mxexplorer = mxexplorer
        self.mxmodelselector = mxmodelselector
        mxexplorer.treeview.shell = self

        self.mxmodelselector.activated.connect(
            lambda : self.update_modeltree(
                self.mxmodelselector.get_selected_model()
            )
        )

    # ---- modelx data view ----
    def set_mxdataview(self, mxdataviewer):
        """Set modelx dataview widget"""
        self.mxdataviewer = mxdataviewer

    def get_obj_value(self, obj: str, args: str,
                      calc: bool=False):

        # logger.debug(f"get_obj_value: {msgtype}, {obj}, {args}, {calc}")

        # jsonargs = TupleEncoder(ensure_ascii=True).encode(args)

        result = cloudpickle.loads(self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_value(
            obj, args, calc
        ))
        return result

    def update_mxdataview(self, obj=None, args=None, expr=None, calc=False):
        """Update dataview"""
        return self.get_obj_value(obj, args, calc)

    # ---- modelx data list ----
    def set_mxdatalist(self, datalist):
        """Set modelx formula list"""
        self.mxdatalist = datalist

    def update_datalist(self):
        """Update codelist"""
        model = self.mxmodelselector.get_selected_model()

        if not model:
            return

        result = self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_value_info(model)
        self.mxdatalist.process_remote_view(result)


    # ---- modelx code list ----
    def set_mxcodelist(self, codelist):
        """Set modelx formula list"""
        self.mxcodelist = codelist

    def update_codelist(self, objname):
        """Update codelist"""

        objname = objname + '.cells'
        data = self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_codelist(objname)

        self.mxcodelist.process_remote_view(data)

    # ---- modelx analyzer ----
    def set_mxanalyzer(self, analyzer):
        """Set modelx dataview widget"""
        self.mxanalyzer = analyzer
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

        return cloudpickle.loads(self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_attrdict(
            fullname=fullname, attrs=attrs, recursive=recursive
        ))

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
        # msgtype = "analyze_" + adjacency + "_setnode"
        obj = tab.attrdict['fullname']
        argtxt = tab.argbox.get_expr()
        args = ast.literal_eval("(" + argtxt + ("," if argtxt else "") + ")")


        try:
            result = cloudpickle.loads(self.call_kernel(
                interrupt=True,
                blocking=True,
                timeout=CALL_KERNEL_TIMEOUT).mx_get_node(
                obj, cloudpickle.dumps(args)))
            # logger.debug(f"_update_mxanalyzer_obj:args: {args}")
            # logger.debug(f"_update_mxanalyzer_obj: {result}")
            self.mxanalyzer.update_status(adjacency, True)
            self.mxanalyzer.update_node(adjacency, result)

        except Exception as e:
            msg = e.__class__.__name__ + ": " + str(e)
            self.mxanalyzer.update_status(adjacency, False, msg)

    def _update_mxanalyzer_expr(self, adjacency):
        """Update dataview"""

        tab = self.mxanalyzer.tabs[adjacency]
        objexpr = tab.exprobjbox.get_expr()
        argexpr = tab.exprargbox.get_expr()

        # Invalid expression
        if objexpr is None or argexpr is None:
            return

        if objexpr:

            # Contribution from bakerwy
            # https://github.com/fumitoh/modelx/discussions/183#discussion-8668563

            try:
                argstr = "(" + argexpr + ("," if argexpr else "") + ")"
                result = cloudpickle.loads(self.call_kernel(
                    interrupt=True, blocking=True,
                    timeout=CALL_KERNEL_TIMEOUT
                ).mx_eval_node(objexpr, argstr))

                self.mxanalyzer.update_status(adjacency, True)
                self.mxanalyzer.update_node(adjacency, result)
            except Exception as e:
                self.mxanalyzer.update_status(
                    adjacency, False, f"{type(e).__name__}: {e}")



    def update_mxanalyzer_all(self):
        for adj in ['precedents', 'succs']:
            self.update_mxanalyzer(adj)

    def get_adjacent(self, obj: str, args: tuple, adjacency: str):

        jsonargs = TupleEncoder(ensure_ascii=True).encode(args)

        result = cloudpickle.loads(self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_adjacent(
            obj, jsonargs, adjacency
        ))
        return result


    # ---- modelx property widget ----
    def set_mxproperty(self, mxproperty):
        """Set modelx dataview widget"""
        mxproperty.shell = self
        self.mxproperty = mxproperty


    def update_mxproperty(self, objname):

        attrs = self.get_attrdict(objname, ['formula', '_evalrepr', 'allow_none', 'parameters'])
        self.mxproperty.process_remote_view(attrs)


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


    def get_modellist(self):

        mlist = self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_get_modellist()


        return mlist

    def update_modeltree(self, name):

        attrs = self.get_attrdict(
            name, ['_is_derived', '__len__', '_evalrepr'], recursive=True)

        # logger.debug(f"Updating modeltree with {attrs}")

        self.mxexplorer.process_remote_view(attrs)


    def new_model(self, name=None, define_var=False, varname=''):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_new_model(
            name, define_var, varname)

        self.update_mx_widgets({})

    def read_model(self, modelpath, name, define_var, varname):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_read_model(
            modelpath, name, define_var, varname)

        self.update_mx_widgets({})

    def new_space(self, model, parent, name, bases, define_var, varname):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_new_space(
            model, parent, name, bases, define_var, varname
        )

        self.update_mx_widgets({})

    def new_cells(self, model, parent, name, formula, define_var, varname):

        if formula:

            try:
                if is_funcdef(formula):
                    pass
                elif is_lambda(formula):
                    pass
                else:
                    QMessageBox.critical(self,
                                         title="Error",
                                         text="Invalid formula")

            except SystemError:
                QMessageBox.critical(self, title="Error", text="Syntax error")
                return

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_new_cells(
            model, parent, name, define_var, varname, formula
        )

        self.update_mx_widgets({})

    def set_formula(self, fullname, formula):

        try:
            if is_funcdef(formula):
                pass
            elif is_lambda(formula):
                pass
            else:
                QMessageBox.critical(self,
                                     title="Error",
                                     text="Invalid formula")
        except SystemError:
            QMessageBox.critical(self, title="Error", text="Syntax error")
            return

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_set_formula(
            fullname, formula
        )

        self.update_mx_widgets({})

    def del_object(self, parent, name):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_del_object(
            parent, name)

        self.update_mx_widgets({})

    def del_model(self, name):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_del_model(
            name)

        self.update_mx_widgets({})

    def write_model(self, model, modelpath, backup, zipmodel):

        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_write_model(
            model, modelpath, backup, zipmodel)

        self.update_mx_widgets({})

    def import_names(self,
                     fullname,
                     import_selected,
                     import_children,
                     replace_existing
    ):
        self.call_kernel(
            interrupt=True,
            blocking=True,
            timeout=CALL_KERNEL_TIMEOUT).mx_import_names(
            fullname, import_selected, import_children, replace_existing)

        self.update_mx_widgets({})





