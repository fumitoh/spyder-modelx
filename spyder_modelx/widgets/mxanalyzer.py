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
                            QLabel)
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt, QObject
from spyder.config.base import _, debug_print
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, create_plugin_layout)
from spyder_modelx.widgets.mxdataview import MxPyExprLineEdit


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
    def __init__(self, data, parent=None, model=None):
        self.parentItem = parent
        self.node = data
        self.isChildLoaded = False
        self.childItems = []
        if model is None:
            self.model = parent.model
        else:
            self.model = model

    def childCount(self):
        return self.node['predslen']

    def hasChildren(self):
        return bool(self.childCount())

    def _reloadChildren(self):
        self.childItems.clear()
        sw = QObject.parent(self.model).shellwidget
        nodes = sw.get_adjacent(self.node['obj']['fullname'],
                                self.node['args'], 'preds')
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
                return ', '.join(str(arg) for arg in self.node['args'])
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


class MxAnalyzerModel(QAbstractItemModel):

    def __init__(self, root=None, parent=None):
        super(MxAnalyzerModel, self).__init__(parent)

        if root is not None:
            self.rootItem = NodeItem(root, parent=None, model=self)
        else:
            self.rootItem = None

    def columnCount(self, parent) -> int:  # Pure virtual

        if not self.rootItem:
            return 0
        else:
            return len(NodeCols)

    def data(self, index, role):    # Pure virtual
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole:
            return item.data(index.column())
        elif role == Qt.TextAlignmentRole:
            col = index.column()
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

        if not parent.isValid():
            childItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

            if row < parentItem.childCount() and column < len(NodeCols):
                childItem = parentItem.getChild(row)
            else:   # must not happen
                raise RuntimeError

        return self.createIndex(row, column, childItem)

    def parent(self, index):    # Pure virtual
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is None:
            return QModelIndex()
        else:
            return self.createIndex(0, 0, parentItem)

    def rowCount(self, parent) -> int:  # Pure virtual

        if self.rootItem is None:
            return 0

        elif not parent.isValid():
            return 1
        else:
            parentItem = parent.internalPointer()
            return parentItem.childCount()

    def insertRows(self, rows, newitem, parent):
        # Signature is different from the base method.

        self.beginInsertRows(parent, rows[0], rows[-1])

        if parent.isValid():
            for row in rows:
                parent.internalPointer().childItems.append(row)
        else:
            self.rootItem = newitem

        self.endInsertRows()

    def removeRows(self, position, rows, parent=QModelIndex()):

        self.beginRemoveRows(parent, position, position + rows - 1)

        if parent.isValid():
            for row in range(position, position + rows):
                parent.internalPointer().childItems.pop(row)
        else:
            self.rootItem = None

        self.endRemoveRows()

    def updateRoot(self, root):
        self.removeRows(0, 1, QModelIndex())
        if root is not None:
            self.insertRows(
                [0], NodeItem(root, None, self), QModelIndex())


class MxAnalyzerWidget(QWidget):

    def __init__(self, parent=None):

        QWidget.__init__(self, parent)
        # self.main = parent # Spyder3

        # Create main widget
        self.model = MxAnalyzerModel(root=None, parent=self)
        self.tree = MxAnalyzerTree(self, self.model)
        self.shellwidget = None

        # Layout of the top area in the plugin widget
        layout_top = QHBoxLayout()
        layout_top.setContentsMargins(0, 0, 0, 0)

        # Add Object textbox
        layout_top.addSpacing(10)
        txt = _("Object")
        if sys.platform == 'darwin':
            obj_label = QLabel("  " + txt)
        else:
            obj_label = QLabel(txt)
        layout_top.addWidget(obj_label)

        self.objbox = MxPyExprLineEdit(self)
        self.objbox.setFont(parent.get_plugin_font())  # TODO: Set in MxPyExpr..
        layout_top.addWidget(self.objbox)
        layout_top.addSpacing(10)

        # Add Object textbox
        txt = _("Args")
        if sys.platform == 'darwin':
            arg_label = QLabel("  " + txt)
        else:
            arg_label = QLabel(txt)
        layout_top.addWidget(arg_label)

        self.argbox = MxPyExprLineEdit(self)
        self.argbox.setFont(parent.get_plugin_font())  # TODO: Set in MxPyExpr..
        layout_top.addWidget(self.argbox)
        layout_top.addSpacing(10)

        # Main layout of this widget
        layout = create_plugin_layout(layout_top, self.tree)
        self.setLayout(layout)

    def set_shellwidget(self, shellwidget):
        """Bind shellwidget instance to namespace browser"""
        self.shellwidget = shellwidget
        shellwidget.set_mxanalyzer(self, self.objbox, self.argbox)


class MxAnalyzerTree(QTreeView):

    def __init__(self, parent, model):
        QTreeView.__init__(self, parent)
        self.setModel(model)
        self.setAlternatingRowColors(True)

    def process_remote_view(self, data):
        model = self.model()
        if data:
            model.updateRoot(data)
        else:
            model.updateRoot(None)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    model = MxAnalyzerModel()

    view = QTreeView()
    view.setModel(model)
    view.setWindowTitle("Simple Tree Model")
    view.show()
    sys.exit(app.exec_())
