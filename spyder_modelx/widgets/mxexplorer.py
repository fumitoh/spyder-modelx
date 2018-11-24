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

from modelx.qtgui.modeltree import ModelTreeModel
from qtpy.QtCore import Signal, Slot, Qt
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox, QAction,
                            QToolButton, QVBoxLayout, QWidget, QTreeView)


class MxTreeView(QTreeView):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.shell = None

        # Context menu
        self.contextMenu = QMenu(self)
        self.action_update_formulas = \
            self.contextMenu.addAction("Update Formulas")

    def contextMenuEvent(self, event):
        action = self.contextMenu.exec_(self.mapToGlobal(event.pos()))

        if action == self.action_update_formulas:
            index = self.currentIndex()
            if index.isValid():
                item = index.internalPointer()
                if item.getType() == 'Space':
                    # QMessageBox(text=item.itemData['fullname']).exec()
                    self.shell.update_codelist(item.itemData['fullname'])


class MxExplorer(QWidget):
    """modelx widget."""

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.setWindowTitle("Mx explorer") # Not visible

        self.treeview = treeview = MxTreeView(self)

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
