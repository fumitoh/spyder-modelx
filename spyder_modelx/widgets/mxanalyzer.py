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

# The source code in this file is modified from:
# https://github.com/baoboa/pyqt5/blob/master/examples/itemviews/simpletreemodel/simpletreemodel.py
# See below for the original copyright notice.

#############################################################################
##
## Copyright (C) 2013 Riverbank Computing Limited.
## Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
## All rights reserved.
##
## This file is part of the examples of PyQt.
##
## $QT_BEGIN_LICENSE:BSD$
## You may use this file under the terms of the BSD license as follows:
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##   * Redistributions of source code must retain the above copyright
##     notice, this list of conditions and the following disclaimer.
##   * Redistributions in binary form must reproduce the above copyright
##     notice, this list of conditions and the following disclaimer in
##     the documentation and/or other materials provided with the
##     distribution.
##   * Neither the name of Nokia Corporation and its Subsidiary(-ies) nor
##     the names of its contributors may be used to endorse or promote
##     products derived from this software without specific prior written
##     permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
## $QT_END_LICENSE$
##
#############################################################################

import sys
import enum
from qtpy.QtWidgets import (QApplication, QTreeView, QWidget, QHBoxLayout,
                            QLabel, QTabWidget, QSplitter, QVBoxLayout,
                            QGridLayout,
                            QButtonGroup, QRadioButton, QMenu)
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt, QObject

import spyder
from spyder.config.base import _, debug_print
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, create_plugin_layout)

if spyder.version_info > (5,):
    from spyder.plugins.variableexplorer.widgets.arrayeditor import ArrayEditor
    from spyder.widgets.collectionseditor import CollectionsEditor
    from spyder.plugins.variableexplorer.widgets.dataframeeditor import DataFrameEditor
elif spyder.version_info > (4,):
    from spyder.plugins.variableexplorer.widgets.arrayeditor import ArrayEditor
    from spyder.plugins.variableexplorer.widgets.collectionseditor import CollectionsEditor
    from spyder.plugins.variableexplorer.widgets.dataframeeditor import DataFrameEditor
else:
    from spyder.widgets.variableexplorer.arrayeditor import ArrayEditor
    from spyder.widgets.variableexplorer.collectionseditor import CollectionsEditor
    from spyder.widgets.variableexplorer.dataframeeditor import DataFrameEditor


from spyder_modelx.utility.tupleencoder import TupleEncoder
from spyder_modelx.widgets.mxlineedit import MxPyExprLineEdit
from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin
from spyder_modelx.widgets.mxcodeeditor import BaseCodePane

class NodeCols(enum.IntEnum):
    Node = 0
    Args = 1
    Value = 2
    Space = 3
    Model = 4


ColAttrs = {NodeCols.Node: {'title': 'Cells',
                            'align': None},     # Default
            NodeCols.Args: {'title': 'Args'},
            NodeCols.Value: {'title': 'Value'},
            NodeCols.Space: {'title': 'Space'},
            NodeCols.Model: {'title': 'Model'}}


class NodeItem(object):
    def __init__(self, data, parent=None, model=None, adjacency=None):
        self.parentItem = parent
        self.node = data
        self.isChildLoaded = False
        self.childItems = []
        if model is None:
            self.model = parent.model
        else:
            self.model = model

        if adjacency:
            self.adjacency = adjacency
        else:
            self.adjacency = parent.adjacency

    def childCount(self):
        if self.isChildLoaded:
            return len(self.childItems)
        else:
            return self.node[self.adjacency + "len"]

    def hasChildren(self):
        return bool(self.childCount())

    def _reloadChildren(self):
        self.childItems.clear()
        sw = self.model.get_shell()
        nodes = sw.get_adjacent(self.node['obj']['fullname'],
                                self.node['args'], self.adjacency)
        items = [NodeItem(node, self) for node in nodes]
        self.childItems.extend(items)
        self.isChildLoaded = True

    def getChild(self, row):
        if not self.isChildLoaded:
            self._reloadChildren()
        return self.childItems[row]

    def data(self, column):
        try:
            if column == NodeCols.Node:
                return self.node['repr']
            elif column == NodeCols.Args:
                if self.node['args']:
                    return ', '.join(str(arg) for arg in self.node['args'])
                else:
                    return ''
            elif column == NodeCols.Value:
                return self.node['value']
            elif column == NodeCols.Space:
                parents = self.node['repr_parent'].split('.')
                if len(parents) > 1:
                    return '.'.join(parents[1:])
                else:
                    return ''
            elif column == NodeCols.Model:
                parents = self.node['repr_parent'].split('.')
                if len(parents):
                    return parents[0]
                else:
                    return ''

        except IndexError:
            return None

    def parent(self):
        return self.parentItem

    @property
    def formula(self):

        if self.node:
            if 'formula' in self.node:
                return self.node['formula']['source']
            if 'obj' in self.node and 'formula' in self.node['obj']:
                return self.node['obj']['formula']['source']
        return ""


class MxAnalyzerModel(QAbstractItemModel):

    def __init__(self, adjacency, root=None, parent=None):
        super(MxAnalyzerModel, self).__init__(parent)

        self.tab = parent
        self.adjacency = adjacency

        if root is None:
            self.rootItem = None
        else:
            self.rootItem = NodeItem(
                root, parent=None, model=self, adjacency=adjacency)
            self.insertRows([0], self.rootItem, parent=QModelIndex())

    def get_shell(self):
        return self.tab.shellwidget

    def rowCount(self, parent) -> int:  # Pure virtual

        if not self.rootItem:
            return 0
        elif parent.isValid():
            parentItem = parent.internalPointer()
            return parentItem.childCount()
        elif self.rootItem:
            return 1
        else:
            return 0

    def columnCount(self, parent) -> int:  # Pure virtual

        if not self.rootItem:
            return 0
        else:
            return len(NodeCols)

    def data(self, index, role):    # Pure virtual
        if not index.isValid():
            return None

        row, col = index.row(), index.column()
        item = index.internalPointer()

        if role == Qt.DisplayRole:
            return item.data(col)
        elif role == Qt.TextAlignmentRole:
            if 'align' in ColAttrs[col]:
                return ColAttrs[col]['align']
            else:
                return Qt.AlignRight
        else:
            return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if self.rootItem:
                return ColAttrs[section]['title']

        return None

    def index(self, row, column, parent):   # Pure virtual

        if row < 0 or column < 0 or not self.rootItem or parent.column() > 0:
            return QModelIndex()

        if row < self.rowCount(parent) and column < self.columnCount(parent):

            if not parent.isValid():
                childItem = self.rootItem
            else:
                parentItem = parent.internalPointer()
                childItem = parentItem.getChild(row)

            return self.createIndex(row, column, childItem)

        else:
            return QModelIndex()

    def parent(self, index):    # Pure virtual
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is None:
            return QModelIndex()
        else:
            return self.createIndex(0, 0, parentItem)

    def insertRows(self, rows, newitem, parent):
        # Currently called only when setting root (parent is invalid)
        # Signature is different from the base method.

        if len(rows) < 1:
            return

        self.beginInsertRows(parent, rows[0], rows[-1])

        if parent.isValid():
            # for row in rows:
            #     parent.internalPointer().childItems.append(row)
            raise RuntimeError('not implemented')
        else:
            self.rootItem = newitem

        self.endInsertRows()

    def removeRows(self, position, rows, parent=QModelIndex()):

        if rows < 1:
            return

        self.beginRemoveRows(parent, position, position + rows - 1)

        if parent.isValid():
            for row in range(position, position + rows):
                parent.internalPointer().childItems.pop(row)
        else:
            self.rootItem = None

        self.endRemoveRows()


class AnalyzerCodePane(BaseCodePane):

    def __init__(self, parent, title=''):
        super().__init__(parent, title)
        self.editor.setReadOnly(True)

    def setCode(self, code):
        self.editor.set_text(code)


class MxAnalyzerTab(QSplitter):

    def __init__(self, parent, adjacency):

        QSplitter.__init__(self, parent, orientation=Qt.Vertical)

        self.plugin = parent.plugin
        self.adjacency = adjacency

        treepane = QWidget(parent=self)

        # Create main widget
        self.model = MxAnalyzerModel(
            adjacency=adjacency,
            root=None,
            parent=self     # parent must be self,
                            # because self.model access self.tab
        )
        # from .modeltest import ModelTest
        # self.modeltest = ModelTest(self.model, self)
        self.tree = MxAnalyzerTree(treepane, self.model)
        self.shellwidget = None # Set by parent

        button_group = QButtonGroup(parent=self)
        self.object_radio = object_radio = QRadioButton("Object")
        self.expr_radio = expr_radio = QRadioButton("Expression")
        button_group.addButton(object_radio)
        button_group.addButton(expr_radio)
        object_radio.setChecked(True)

        object_radio.toggled.connect(self.toggleObject)

        # Layout of the top area in the plugin widget
        expr_layout = QHBoxLayout()
        expr_layout.setContentsMargins(0, 0, 0, 0)

        # Add Object textbox
        expr_layout.addSpacing(10)
        txt = _("Object")
        if sys.platform == 'darwin':
            obj_label = QLabel("  " + txt)
        else:
            obj_label = QLabel(txt)
        expr_layout.addWidget(obj_label)

        if spyder.version_info < (4,):
            font = parent.plugin.get_plugin_font()
        else:
            font = parent.plugin.get_font()

        self.objbox = QLabel(parent=self)
        self.argbox = MxPyExprLineEdit(self, font=font)
        self.attrdict = None

        objbox_layout = QHBoxLayout()
        objbox_layout.addWidget(self.objbox)
        objbox_layout.addWidget(self.argbox)
        objbox_layout.setStretch(0, 3)  # 3:1
        objbox_layout.setStretch(1, 1)

        self.exprobjbox = MxPyExprLineEdit(treepane, font=font)
        expr_layout.addWidget(self.exprobjbox)
        expr_layout.addSpacing(10)

        # Add Object textbox
        txt = _("Args")
        if sys.platform == 'darwin':
            arg_label = QLabel("  " + txt)
        else:
            arg_label = QLabel(txt)
        expr_layout.addWidget(arg_label)

        self.exprargbox = MxPyExprLineEdit(treepane, font=font)
        expr_layout.addWidget(self.exprargbox)
        # expr_layout.addSpacing(5)

        top_layout = QGridLayout()
        top_layout.addWidget(object_radio, 0, 0)
        top_layout.addWidget(expr_radio, 1, 0)
        top_layout.addLayout(objbox_layout, 0, 1)
        objbox_layout.setContentsMargins(0, 0, 0, 5)
        top_layout.addLayout(expr_layout, 1, 1)
        top_layout.setContentsMargins(5, 5, 5, 5)

        # Main layout of this widget
        layout = create_plugin_layout(top_layout, self.tree)
        treepane.setLayout(layout)

        self.status = QLabel()
        layout.addWidget(self.status)

        self.codepane = AnalyzerCodePane(parent=self)

    def replace_model(self, data):

        model = MxAnalyzerModel(
            adjacency=self.adjacency,
            parent=self,
            root=data
        )
        self.model = model
        self.tree.setModel(model)

    def toggleObject(self, checked):

        if checked:
            self.exprobjbox.setEnabled(False)
            self.exprargbox.setEnabled(False)
        else:
            self.argbox.setEnabled(False)
            self.exprobjbox.setEnabled(True)
            self.exprargbox.setEnabled(True)

        self.shellwidget.update_mxanalyzer(self.adjacency, update_attrdict=False)

    def set_argbox(self):
        if self.attrdict:
            if _has_param(self.attrdict):
                self.argbox.setEnabled(True)
            else:
                self.argbox.setEnabled(False)
        else:
            self.argbox.setText("")
            self.argbox.setEnabled(False)

    def clear_obj(self):
        self.attrdict = None
        self.set_argbox()
        self.objbox.setText('')
        self.replace_model(None)


def _has_param(data):
    type_ = data["type"]

    if type_ == "Reference":
        return False
    elif type_ == "Cells":
        if data["parameters"]:
            return True
        else:
            return False
    else:
        raise RuntimeError("must not happen")


if spyder.version_info > (5,):

    class MxAnalyzerWidget(QWidget):

        def __init__(self, parent, **kwargs):
            QWidget.__init__(self, parent)

            self.plugin = parent.get_plugin()

            # Create main widget
            self.tabwidget = QTabWidget(parent=parent)
            self.precedents = MxAnalyzerTab(parent=self, adjacency='precedents')
            self.succs = MxAnalyzerTab(parent=self, adjacency='succs')
            self.tabs = {'precedents': self.precedents,
                         'succs': self.succs}

            self.tabwidget.addTab(self.precedents, 'Precedents')
            self.tabwidget.addTab(self.succs, 'Dependents')

            # Main Layout
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.tabwidget)
            self.setLayout(layout)

            self.setFocusPolicy(Qt.ClickFocus)

        def set_shellwidget(self, shellwidget):
            """Bind shellwidget instance to namespace browser"""
            self.shellwidget = shellwidget
            for tab in self.tabs.values():
                tab.shellwidget = shellwidget
            shellwidget.set_mxanalyzer(self)

        def update_object(self, data, analyze=True):
            if data is None:
                return

            tab = self.tabwidget.currentWidget()

            tab.attrdict = data
            if not _has_param(data):
                tab.argbox.setText("")

            tab.objbox.setText(data['_evalrepr'])

            if analyze:
                tab.object_radio.setChecked(True)
                tab.toggleObject(True)

        # Slot
        def update_node(self, adjacency, data):
            tab = self.tabs[adjacency]
            tab.replace_model(data)

        def update_status(self, adjacency, success, msg=''):
            tab = self.tabs[adjacency]
            if success:
                tab.status.setText(msg)
            else:
                tab.status.setText(msg)
                tab.replace_model(None)

else:
    class MxAnalyzerWidget(MxToolBarMixin, QWidget):

        def __init__(self, parent, **kwargs):
            QWidget.__init__(self, parent)

            if spyder.version_info > (5,):
                self.plugin = parent.get_plugin()
            else:
                self.plugin = parent

            # Create tool bar
            if "options_button" in kwargs:
                self.options_button = kwargs["options_button"]
            else:
                self.options_button = None
            self.plugin_actions = []
            MxToolBarMixin.__init__(
                self,
                options_button=self.options_button,
                plugin_actions=self.plugin_actions
            )

            # Create main widget
            self.tabwidget = QTabWidget(parent=parent)
            self.precedents = MxAnalyzerTab(parent=self, adjacency='precedents')
            self.succs = MxAnalyzerTab(parent=self, adjacency='succs')
            self.tabs = {'precedents': self.precedents,
                         'succs': self.succs}

            self.tabwidget.addTab(self.precedents, 'Precedents')
            self.tabwidget.addTab(self.succs, 'Dependents')

            layout = create_plugin_layout(self.tools_layout, self.tabwidget)
            self.setFocusPolicy(Qt.ClickFocus)
            self.setLayout(layout)

        def set_shellwidget(self, shellwidget):
            """Bind shellwidget instance to namespace browser"""
            self.shellwidget = shellwidget
            for tab in self.tabs.values():
                tab.shellwidget = shellwidget
            shellwidget.set_mxanalyzer(self)

        def update_object(self, data, analyze=True):
            if data is None:
                return

            tab = self.tabwidget.currentWidget()

            tab.attrdict = data
            if not _has_param(data):
                tab.argbox.setText("")

            tab.objbox.setText(data['_evalrepr'])

            if analyze:
                tab.object_radio.setChecked(True)
                tab.toggleObject(True)

        # Slot
        def update_node(self, adjacency, data):
            tab = self.tabs[adjacency]
            tab.replace_model(data)

        def update_status(self, adjacency, success, msg=''):
            tab = self.tabs[adjacency]
            if success:
                tab.status.setText(msg)
            else:
                tab.status.setText(msg)
                tab.replace_model(None)


class MxAnalyzerTree(QTreeView):

    def __init__(self, parent, model):
        QTreeView.__init__(self, parent)
        self.setModel(model)
        self.setAlternatingRowColors(True)
        self.doubleClicked.connect(self.doubleClicked_callback)

        # Context menu
        self.contextMenu = QMenu(self)

        self.action_show_value = self.contextMenu.addAction(
            "Show Value"
        )

    def contextMenuEvent(self, event):
        action = self.contextMenu.exec_(self.mapToGlobal(event.pos()))

        if action == self.action_show_value:
            current = self.currentIndex()

            if current.isValid():
                # replace column
                idx = self.model().index(
                    current.row(), NodeCols.Value, current.parent())

                self.doubleClicked_callback(idx)


    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        if current.isValid():
            item = current.internalPointer()
            self.parent().parent().codepane.setCode(item.formula)

    def doubleClicked_callback(self, index: QModelIndex):

        import pandas as pd
        import numpy as np
        import numpy.ma

        if index.isValid() and index.column() == NodeCols.Value:

            item = index.internalPointer()
            obj = item.node['obj']['fullname']
            args = str(item.node['args'])

            data, _ = self.shell.get_obj_value(
                'analyze_getval', obj, args)

            if isinstance(data, (pd.DataFrame, pd.Index, pd.Series)):
                dialog = DataFrameEditor(self)
                dialog.setup_and_check(data)
            elif isinstance(data, (np.ndarray, np.ma.MaskedArray)):
                dialog = ArrayEditor(self)
                dialog.setup_and_check(data, title='', readonly=True)
            elif isinstance(data, (list, set, tuple, dict)):
                dialog = CollectionsEditor(self)
                dialog.setup(data, title='', readonly=True)
            else:
                return

            dialog.show()

    @property
    def shell(self):
        return self.parent().parent().shellwidget


if __name__ == '__main__':
    app = QApplication(sys.argv)
    model = MxAnalyzerModel()

    view = QTreeView()
    view.setModel(model)
    view.setWindowTitle("Simple Tree Model")
    view.show()
    sys.exit(app.exec_())
