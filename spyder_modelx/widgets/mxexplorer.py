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
import sys

from spyder_modelx.widgets.mxtreemodel import MxTreeModel, ModelItem
from qtpy.QtCore import Signal, Slot, Qt, QStringListModel
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox, QAction,
                            QToolButton, QVBoxLayout, QWidget, QTreeView,
                            QSplitter, QComboBox)
import spyder
from spyder.config.base import _
from spyder.utils.qthelpers import create_plugin_layout
from spyder_modelx.widgets.mxcodelist import MxCodeListWidget
from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin


class MxTreeView(QTreeView):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.shell = None

        # Context menu
        self.contextMenu = QMenu(self)
        self.action_update_formulas = \
            self.contextMenu.addAction("Show Formulas")

        self.setAlternatingRowColors(True)

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.treeview)
        self.setLayout(layout)

    def process_remote_view(self, data):
        if data:
            model = self.treeview.model()
            if model:
                if model.modelid == data['id']:
                    if model.rootItem.itemData != data:
                        model.updateRoot(ModelItem(data))
                else:
                    self.treeview.setModel(MxTreeModel(ModelItem(data)))
            else:
                self.treeview.setModel(MxTreeModel(ModelItem(data)))
        else:
            self.treeview.setModel(None)


class MxMainWidget(MxToolBarMixin, QWidget):

    def __init__(self, parent, **kwargs):
        QWidget.__init__(self, parent)

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

        # Create widget and add to dockwindow
        self.explorer = MxExplorer(self)

        # Create code list
        self.codelist = MxCodeListWidget(self)

        # Create splitter
        self.splitter = QSplitter(self)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        # self.splitter.addWidget(self.widget)
        # self.splitter.setStretchFactor(0, 5)
        # self.splitter.setStretchFactor(1, 1)

        # Layout management
        self.splitter.addWidget(self.explorer)
        self.splitter.addWidget(self.codelist)

        layout = create_plugin_layout(self.tools_layout, self.splitter)

        self.setFocusPolicy(Qt.ClickFocus)
        self.setLayout(layout)

    def set_shellwidget(self, shellwidget):
        """Bind shellwidget instance to namespace browser"""
        self.shellwidget = shellwidget
        self.shellwidget.set_mxexplorer(self.explorer, self.model_selector)
        self.shellwidget.set_mxcodelist(self.codelist)

    # MxToolBarMixin interface method
    def setup_toolbar(self):

        txt = _("Model")
        if sys.platform == 'darwin':
            expr_label = QLabel("  " + txt)
        else:
            expr_label = QLabel(txt)

        if spyder.version_info < (4,):
            font = self.plugin.get_plugin_font()
        else:
            font = self.plugin.get_font()

        self.model_selector = MxModelSelector(self)

        return [expr_label, self.model_selector]


class MxModelSelector(QComboBox):

    sig_mxmodelselected = Signal()

    def __init__(self, parent):
        QComboBox.__init__(self, parent=parent)

        # modellist is a list of dicts that contains basic model attributes.
        # The first element represents the current model,
        # and it can be None if no current model is set.
        self.modellist = []


    def get_selected_model(self, modellist=None):
        """Gets the name of the selected model."""

        if modellist:
            self.update_modellist(modellist)

        idx = self.currentIndex()
        if idx < 0:
            return ""
        elif idx == 0 and not self.modellist[idx]:
            return ""
        else:
            m = self.modellist[idx]
            return m["name"]

    def update_modellist(self, modellist):
        """Update the list of models.

        modellist can be [None, ...]

        if the current model is previously selected, select the current model
        after updating.
        if the previously selected model does not exist after updating,
        the current model is selected.
        """

        if not self.is_modellist_updated(modellist):
            return

        idx = self.currentIndex()

        if idx > 0:
            modelid = self.modellist[idx]["id"]

        textlist = []
        newidx = 0
        for i, m in enumerate(modellist):
            if not i:   # Current model
                modelname = m["name"] if m else "None"
                textlist.append("Current Model - %s" % modelname)
            else:
                if idx > 0 and m["id"] == modelid:
                    newidx = i
                textlist.append(m["name"])

        self.clear()
        self.addItems(textlist)

        if idx > 0:
            self.setCurrentIndex(newidx)

        self.modellist = modellist

    def is_modellist_updated(self, modellist):

        if len(self.modellist) != len(modellist):
            return True

        for cur, oth in zip(self.modellist, modellist):
            if cur is None:
                if oth is None:
                    continue
                else:
                    return True
            if cur["name"] == oth["name"] and cur["id"] == oth["id"]:
                continue
            else:
                return True

        return False

