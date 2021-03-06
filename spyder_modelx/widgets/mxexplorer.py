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
import sys, os
import keyword
from qtpy.QtCore import Signal, Slot, Qt, QStringListModel, QEventLoop
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox, QAction,
                            QToolButton, QVBoxLayout, QWidget, QTreeView,
                            QSplitter, QComboBox, QSizePolicy, QDialog,
                            QGridLayout, QListWidget, QPushButton,
                            QDialogButtonBox, QLineEdit, QCheckBox, QTabWidget)
from qtpy.QtGui import QPalette
from qtpy.compat import getexistingdirectory, getopenfilename
import spyder
from spyder.py3compat import to_text_string
from spyder.config.base import _
from spyder.utils.qthelpers import create_plugin_layout
from spyder.utils.misc import getcwd_or_home
from spyder.utils import icon_manager as ima
from spyder_modelx.widgets.mxcodelist import MxCodeListWidget
from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin
from spyder_modelx.widgets.mxcodeeditor import BaseCodePane
from spyder_modelx.widgets.mxproperty import MxPropertyWidget
from spyder_modelx.widgets.mxtreemodel import (
    MxTreeModel, ModelItem, ItemSpaceItem,
    ViewItem, SpaceItem, CellsItem, RefItem)


class MxTreeView(QTreeView):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.activated.connect(self.activated_callback)

        self.plugin = parent.plugin
        self.shell = None
        self.reply = None  # To write dialog box result
        self.setAlternatingRowColors(False)

        # Context menu
        self.contextMenu = QMenu(self)

        self.action_update_properties = self.contextMenu.addAction(
            "Show Properties"
        )
        self.action_import_names = self.contextMenu.addAction(
            "Import Names"
        )
        self.action_update_formulas = self.contextMenu.addAction(
            "Show Formulas"
        )
        self.action_new_model = self.contextMenu.addAction(
            "Create New Model"
        )
        self.action_new_space = self.contextMenu.addAction(
            "Create New Space"
        )
        self.action_new_cells = self.contextMenu.addAction(
            "Create New Cells"
        )
        self.action_read_model = self.contextMenu.addAction(
            "Read Model"
        )
        self.action_write_model = self.contextMenu.addAction(
            "Write Model"
        )
        self.action_delete_selected = self.contextMenu.addAction(
            "Delete Selected"
        )
        self.action_delete_model = self.contextMenu.addAction(
            "Delete Model"
        )

    def activated_callback(self, index):
        if index.isValid():
            item = self.currentIndex().internalPointer()
            if not isinstance(item, ViewItem):
                self.shell.update_mxproperty(item.itemData['fullname'])

    def contextMenuEvent(self, event):
        action = self.contextMenu.exec_(self.mapToGlobal(event.pos()))

        if action == self.action_update_formulas:
            index = self.currentIndex()
            if index.isValid():
                item = index.internalPointer()
                if isinstance(item, SpaceItem):
                    pass
                else:
                    if index.parent().isValid():
                        item = index.parent().internalPointer()
                    else:
                        return

                self.shell.update_codelist(item.itemData['fullname'])

        elif action == self.action_update_properties:
            index = self.currentIndex()
            if index.isValid():
                item = self.currentIndex().internalPointer()
                if not isinstance(item, ViewItem):
                    self.shell.update_mxproperty(item.itemData['fullname'])

        elif action == self.action_import_names:
            index = self.currentIndex()
            if index.isValid():
                item = self.currentIndex().internalPointer()

                if isinstance(item, SpaceItem):
                    has_children = True
                elif isinstance(item, CellsItem) or isinstance(item, RefItem):
                    has_children = False
                else:
                    return
            else:
                return

            if has_children:
                dialog = ImportNamesDialog(self)
                dialog.exec()

                if self.reply['accepted']:
                    import_selected = self.reply['import_selected']
                    import_children = self.reply['import_children']
                    replace_existing = self.reply['replace_existing']
                    self.reply = None
                else:
                    self.reply = None
                    return
            else:
                import_selected = True
                import_children = False
                replace_existing = True

            self.shell.import_names(item.itemData['fullname'],
                                    import_selected,
                                    import_children,
                                    replace_existing
                                    )


        elif action == self.action_new_model:
            dialog = NewModelDialog(self)
            dialog.exec()

            if self.reply['accepted']:
                name = self.reply['name']
                define_var = self.reply['define_var']
                if define_var:
                    varname = self.reply['varname']
                else:
                    varname = ''
                self.reply = None
                self.shell.new_model(name, define_var, varname)
            else:
                self.reply = None

        elif action == self.action_new_space:
            if self.model():
                parentList = self.model().rootItem.getSpaceContainerList()
            else:
                parentList = []

            # Find current item
            index = self.currentIndex()
            if index.isValid():
                name = index.internalPointer().itemData['fullname']
                try:
                    currIndex = parentList.index(name)
                except ValueError:
                    currIndex = 0
            else:
                currIndex = 0

            if self.model():
                model = self.model().rootItem.itemData['name']
            else:
                model = ''

            dialog = NewSpaceDialog(self, parentList, currIndex)
            dialog.exec()

            if self.reply['accepted']:
                name = self.reply['name']
                parent = self.reply['parent']
                bases = self.reply['bases']
                define_var = self.reply['define_var']
                if define_var:
                    varname = self.reply['varname']
                else:
                    varname = ''
                self.reply = None
                self.shell.new_space(
                    model, parent, name, bases, define_var, varname)
            else:
                self.reply = None

        elif action == self.action_new_cells:
            if self.model():
                parentList = self.model().rootItem.getChildSpaceList()
            else:
                parentList = []

            # Find current item
            index = self.currentIndex()
            if index.isValid():
                name = index.internalPointer().itemData['namedid']
                try:
                    currIndex = parentList.index(name)
                except ValueError:
                    currIndex = 0
            else:
                currIndex = 0

            if self.model():
                model = self.model().rootItem.itemData['name']
            else:
                model = ''

            dialog = NewCellsDialog(self, parentList, currIndex)
            dialog.exec()

            if self.reply['accepted']:
                name = self.reply['name']
                parent = self.reply['parent']
                formula = self.reply['formula']
                define_var = self.reply['define_var']
                if define_var:
                    varname = self.reply['varname']
                else:
                    varname = ''
                self.reply = None
                self.shell.new_cells(
                    model, parent, name, formula, define_var, varname)
            else:
                self.reply = None

        elif action == self.action_read_model:
            dialog = ReadModelDialog(self)
            dialog.exec()

            if self.reply['accepted']:
                modelpath = self.reply['directory']
                name = self.reply['name']
                define_var = self.reply['define_var']
                if define_var:
                    varname = self.reply['varname']
                else:
                    varname = ''
                self.reply = None
                self.shell.read_model(modelpath, name, define_var, varname)
            else:
                self.reply = None

        elif action == self.action_write_model:
            model = self.plugin.current_widget().model_selector.get_selected_model()
            if not model:
                QMessageBox.critical(self, "Error", "No model exits.")
                return

            dialog = WriteModelDialog(self)
            dialog.exec()

            if self.reply['accepted']:
                modelpath = self.reply['directory'] + "/" + self.reply['name']
                backup = self.reply['backup']
                self.reply = None
                self.shell.write_model(model, modelpath, backup)
            else:
                self.reply = None

        elif action == self.action_delete_model:
            model = self.plugin.current_widget().model_selector.get_selected_model()
            if model:
                answer = QMessageBox.question(
                    self, _("Delete Model"),
                    _("Do you want to delete %s?" % model),
                    QMessageBox.Yes | QMessageBox.No)
                if answer == QMessageBox.Yes:
                    self.shell.del_model(model)
                else:
                    return
            else:
                QMessageBox.critical(self, "Error", "No model exits.")
        elif action == self.action_delete_selected:
            index = self.currentIndex()
            if index.isValid():
                item = index.internalPointer()
                if isinstance(item, ViewItem) or isinstance(item, ItemSpaceItem):
                    pass
                else:
                    if index.parent().isValid():
                        parent = index.parent().internalPointer().fullname
                        self.shell.del_object(parent, item.name)
                    else:
                        parent = self.plugin.current_widget().model_selector.get_selected_model()
                        if parent:
                            self.shell.del_object(parent, item.name)
                        else:
                            raise RuntimeError("must not happen")

                    QMessageBox.information(
                        self, "Notice",
                        "'%s' is deleted from '%s'" % (item.name, parent))


class MxExplorer(QWidget):
    """modelx widget."""

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.plugin = parent.plugin
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
        self.propwidget = MxPropertyWidget(self)

        # Create splitter
        self.splitter = QSplitter(self)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        # self.splitter.addWidget(self.widget)
        # self.splitter.setStretchFactor(0, 5)
        # self.splitter.setStretchFactor(1, 1)

        self.tabwidget = QTabWidget(parent=self)
        # self.tabwidget.setContentsMargins(0, 0, 0, 0)
        MxMainWidget.IdxProperties = self.tabwidget.addTab(self.propwidget, "Properties")
        MxMainWidget.IdxFormulas = self.tabwidget.addTab(self.codelist, "Formulas")

        # Layout management
        self.splitter.addWidget(self.explorer)
        self.splitter.addWidget(self.tabwidget)

        layout = create_plugin_layout(self.tools_layout, self.splitter)

        self.setFocusPolicy(Qt.ClickFocus)
        self.setLayout(layout)

    def set_shellwidget(self, shellwidget):
        """Bind shellwidget instance to namespace browser"""
        self.shellwidget = shellwidget
        self.shellwidget.set_mxexplorer(self.explorer, self.model_selector)
        self.shellwidget.set_mxcodelist(self.codelist)
        self.shellwidget.set_mxproperty(self.propwidget)

    def raise_tab(self, widget):
        self.tabwidget.setCurrentWidget(widget)

    # MxToolBarMixin interface method
    def setup_toolbar(self):

        txt = _("Model")
        if sys.platform == 'darwin':
            expr_label = QLabel("  " + txt)
        else:
            expr_label = QLabel(txt)

        expr_label.setAlignment(Qt.AlignCenter | Qt.AlignRight)

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


class ImportNameEdit(QLineEdit):

    def __init__(self, parent):
        super().__init__(parent)
        self.synced = True

    def focusInEvent(self, a0) -> None:
        self.synced = False
        super().focusInEvent(a0)


class ImportAsWidget(QWidget):

    def __init__(self, parent, sourceWidget: QLineEdit):
        super().__init__(parent)

        self.sourceWidget = sourceWidget
        self.shouldImport = QCheckBox(_("Import As"))
        self.shouldImport.setCheckState(Qt.Checked)
        self.shouldImport.stateChanged.connect(self.activateName)

        self.nameEdit = ImportNameEdit(self)
        sourceWidget.textChanged.connect(self.syncText)

        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.shouldImport)
        self.layout.addWidget(self.nameEdit)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # https://forum.qt.io/topic/87226/synchronize-2-qlineedit

    def syncText(self, name):
        if self.shouldImport.isChecked() and self.nameEdit.synced:
            self.nameEdit.setText(name)

    def activateName(self, state):
        if state:
            self.nameEdit.setReadOnly(False)
            self.nameEdit.setEnabled(True)
        else:
            self.nameEdit.setReadOnly(True)
            self.nameEdit.setEnabled(False)


def check_varname(varname):
    if varname:
        if varname.isidentifier():
            if keyword.iskeyword(varname):
                return False
            else:
                return True
        else:
            return False
    else:   # True if empty
        return True


class NewModelDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle('Create New Model')
        self.treeview = parent
        self.setAttribute(Qt.WA_DeleteOnClose)

        namelabel = QLabel(_("Model Name"))
        self.nameEdit = QLineEdit(self)
        self.importWidget = ImportAsWidget(self, self.nameEdit)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(namelabel, 0, 0)
        mainLayout.addWidget(self.nameEdit, 0, 1)
        mainLayout.addWidget(self.importWidget, 1, 0, 1, 2)
        mainLayout.addWidget(self.buttonBox, 2, 0, 1, 2)
        self.setLayout(mainLayout)

    def accept(self) -> None:
        reply = {
            'accepted': True,
            'name': self.nameEdit.text(),
            'define_var': self.importWidget.shouldImport.isChecked(),
            'varname': self.importWidget.nameEdit.text()
        }
        if reply['define_var']:
            varname = reply['varname']
            if not check_varname(varname):
                QMessageBox.critical(
                    self,
                    'Error',
                    'Invalid variable name: %s' % varname
                )
                return
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {'accepted': False}
        super().reject()


class ReadModelDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle('Read Model')
        self.treeview = parent
        self.setAttribute(Qt.WA_DeleteOnClose)

        fixed_dir_layout = QHBoxLayout()
        browse_btn = QPushButton(ima.icon('DirOpenIcon'), '', self)
        browse_btn.setToolTip(_("Select model directory"))
        browse_btn.clicked.connect(self.select_model)
        self.wd_edit = QLineEdit()
        fixed_dir_layout.addWidget(self.wd_edit)
        fixed_dir_layout.addWidget(browse_btn)
        fixed_dir_layout.setContentsMargins(0, 0, 0, 0)

        namelabel = QLabel(_("Model Name"))
        self.nameEdit = QLineEdit(self)
        self.importWidget = ImportAsWidget(self, self.nameEdit)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addLayout(fixed_dir_layout, 0, 0, 1, 2)
        mainLayout.addWidget(namelabel, 1, 0)
        mainLayout.addWidget(self.nameEdit, 1, 1)
        mainLayout.addWidget(self.importWidget, 2, 0, 1, 2)
        mainLayout.addWidget(self.buttonBox, 3, 0, 1, 2)
        # mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

    def accept(self) -> None:
        reply = {
            'accepted': True,
            'directory': self.wd_edit.text(),
            'name': self.nameEdit.text(),
            'define_var': self.importWidget.shouldImport.isChecked(),
            'varname': self.importWidget.nameEdit.text()
        }
        if reply['define_var']:
            varname = reply['varname']
            if not check_varname(varname):
                QMessageBox.critical(
                    self,
                    'Error',
                    'Invalid variable name: %s' % varname
                )
                return
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {'accepted': False}
        super().reject()

    def select_directory(self):
        """Select directory (Not Used)"""
        basedir = to_text_string(self.wd_edit.text())
        if not os.path.isdir(basedir):
            basedir = getcwd_or_home()
        directory = getexistingdirectory(self, _("Select directory"), basedir)
        if directory:
            self.wd_edit.setText(directory)

    def select_model(self):
        """Select Model file/dir"""
        basedir = to_text_string(self.wd_edit.text())
        if not os.path.isdir(basedir):
            basedir = getcwd_or_home()
        file, no_use = getopenfilename(self, _("Select Model"), basedir)
        if file:
            self.wd_edit.setText(file)


class WriteModelDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle('Write Model')
        self.treeview = parent
        self.setAttribute(Qt.WA_DeleteOnClose)

        fixed_dir_layout = QHBoxLayout()
        browse_btn = QPushButton(ima.icon('DirOpenIcon'), '', self)
        browse_btn.setToolTip(_("Select model directory"))
        browse_btn.clicked.connect(self.select_directory)
        self.wd_edit = QLineEdit()
        fixed_dir_layout.addWidget(self.wd_edit)
        fixed_dir_layout.addWidget(browse_btn)
        fixed_dir_layout.setContentsMargins(0, 0, 0, 0)

        namelabel = QLabel(_("Folder Name"))
        self.nameEdit = QLineEdit(self)

        self.backupCheck = QCheckBox(_("Back up old folder"))
        self.backupCheck.setCheckState(Qt.Checked)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addLayout(fixed_dir_layout, 0, 0, 1, 2)
        mainLayout.addWidget(namelabel, 1, 0)
        mainLayout.addWidget(self.nameEdit, 1, 1)
        mainLayout.addWidget(self.backupCheck, 2, 0, 1, 2)
        mainLayout.addWidget(self.buttonBox, 3, 0, 1, 2)
        # mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

    def accept(self) -> None:
        reply = {
            'accepted': True,
            'directory': self.wd_edit.text(),
            'name': self.nameEdit.text(),
            'backup': self.backupCheck.isChecked()
        }
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {'accepted': False}
        super().reject()

    def select_directory(self):
        """Select directory"""
        basedir = to_text_string(self.wd_edit.text())
        if not os.path.isdir(basedir):
            basedir = getcwd_or_home()
        directory = getexistingdirectory(self, _("Select directory"), basedir)
        if directory:
            self.wd_edit.setText(directory)


class NewSpaceDialog(QDialog):

    def __init__(self, parent=None, parentList=(), currIndex=0):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle('Create New Space')
        self.treeview = parent
        self.reply = None

        parentLabel = QLabel(_("Parent"))
        self.parentBox = QComboBox(self)
        self.parentBox.addItems(parentList)
        self.parentBox.setCurrentIndex(currIndex)

        nameLabel = QLabel(_("Space Name"))
        self.nameEdit = QLineEdit(self)
        self.importWidget = ImportAsWidget(self, self.nameEdit)

        basesTitle = QLabel(_("Base Spaces"))
        self.basesLine = QLineEdit()
        self.basesLine.setReadOnly(True)
        self.basesLine.setEnabled(False)
        self.basesEditButton = QPushButton(_("Edit"))
        self.basesEditButton.clicked.connect(self.on_base_edit)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(parentLabel, 0, 0)
        mainLayout.addWidget(self.parentBox, 0, 1)
        mainLayout.addWidget(nameLabel, 1, 0)
        mainLayout.addWidget(self.nameEdit, 1, 1)
        mainLayout.addWidget(self.importWidget, 2, 0, 1, 2)
        mainLayout.addWidget(basesTitle, 3, 0)
        mainLayout.addWidget(self.basesLine, 3, 1)
        mainLayout.addWidget(self.basesEditButton, 3, 2)
        mainLayout.addWidget(self.buttonBox, 4, 0, 1, 2)
        self.setLayout(mainLayout)

    def accept(self) -> None:

        reply = {
            'accepted': True,
            'parent': self.parentBox.currentText(),
            'name': self.nameEdit.text(),
            'bases': self.basesLine.text(),
            'define_var': self.importWidget.shouldImport.isChecked(),
            'varname': self.importWidget.nameEdit.text()
        }
        if reply['define_var']:
            varname = reply['varname']
            if not check_varname(varname):
                QMessageBox.critical(
                    self,
                    'Error',
                    'Invalid variable name: %s' % varname
                )
                return
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {'accepted': False}
        super().reject()

    def on_base_edit(self):
        selected = self.basesLine.text().strip()
        if selected:
            selected = [base.strip() for base in selected.split(",")]
        else:
            selected = []

        if self.treeview.model():
            allItems = self.treeview.model().rootItem.getChildSpaceList()
        else:
            allItems = []

        dialog = SelectBaseSpacesDialog(
            self,
            allItems=allItems,
            selectedItems=selected
        )
        dialog.exec()
        if self.reply['accepted']:
            self.basesLine.setText(self.reply['value'])


class SelectFromListDialog(QDialog):
    """Dialog box for selecting multiple items.

    The original order of items are preserved in the candidate list.
    """

    def __init__(self, parent=None, allItems=(), selectedItems=()):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.allItems = allItems

        self.fromKeys = list(range(len(allItems)))
        self.selectedKeys = []
        for item in selectedItems:
            key = allItems.index(item)
            self.fromKeys.remove(key)
            self.selectedKeys.append(key)

        self.setAttribute(Qt.WA_DeleteOnClose)

        fromLabel = QLabel(_("Select from"))
        self.fromList = QListWidget(self)
        self.fromList.addItems(allItems[key] for key in self.fromKeys)

        selectedLabel = QLabel(_("Selected"))
        self.selectedList = QListWidget(self)
        self.selectedList.addItems(allItems[key] for key in self.selectedKeys)

        self.selectButton = QPushButton(_("Select"))
        self.deselectButton = QPushButton(_("Deselect"))
        self.selectBox = QDialogButtonBox(Qt.Vertical)
        self.selectBox.addButton(self.selectButton, QDialogButtonBox.ActionRole)
        self.selectBox.addButton(self.deselectButton, QDialogButtonBox.ActionRole)
        self.selectButton.clicked.connect(self.on_select)
        self.deselectButton.clicked.connect(self.on_deselect)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(fromLabel, 0, 0)
        mainLayout.addWidget(selectedLabel, 0, 2)
        mainLayout.addWidget(self.fromList, 1, 0)
        mainLayout.addWidget(self.selectBox, 1, 1)
        mainLayout.addWidget(self.selectedList, 1, 2)
        mainLayout.addWidget(self.buttonBox, 2, 0, 1, 3)
        mainLayout.setAlignment(self.selectBox, Qt.AlignCenter)
        self.setLayout(mainLayout)

    def on_select(self):
        if len(self.fromList.selectedItems()):
            idx = self.fromList.currentRow()
            key = self.fromKeys.pop(idx)
            self.selectedKeys.append(key)
            item = self.fromList.takeItem(idx)
            self.selectedList.addItem(item)

    def on_deselect(self):
        if len(self.selectedList.selectedItems()):
            idx = self.selectedList.currentRow()
            item = self.selectedList.takeItem(idx)
            key = self.selectedKeys.pop(idx)
            idx = next((i for i, v in enumerate(self.fromKeys) if v > key),
                       len(self.fromKeys))
            self.fromKeys.insert(idx, key)
            self.fromList.insertItem(idx, item)


class SelectBaseSpacesDialog(SelectFromListDialog):

    def __init__(self, parent=None, allItems=(), selectedItems=()):
        super().__init__(parent, allItems, selectedItems)
        self.setWindowTitle('Create New Space')
        self.parent = parent

    def getSelectedAsString(self):
        result = []
        for idx in range(len(self.selectedKeys)):
            val = self.allItems[self.selectedKeys[idx]]
            result.append(val)

        return ", ".join(result)

    def accept(self) -> None:
        self.parent.reply = {
            'accepted': True,
            'value': self.getSelectedAsString()
        }
        super().accept()

    def reject(self) -> None:
        self.parent.reply = {'accepted': False}
        super().reject()


class NewCellsDialog(QDialog):

    def __init__(self, parent=None, parentList=(), currIndex=0):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle('Create New Cells')
        self.treeview = parent

        parentLabel = QLabel(_("Parent"))
        self.parentBox = QComboBox(self)
        self.parentBox.addItems(parentList)
        self.parentBox.setCurrentIndex(currIndex)

        nameLabel = QLabel(_("Cells Name"))
        self.nameEdit = QLineEdit(self)
        self.importWidget = ImportAsWidget(self, self.nameEdit)

        self.formulaPane = BaseCodePane(parent, title='Formula')
        self.formulaPane.editor.setReadOnly(False)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(parentLabel, 0, 0)
        mainLayout.addWidget(self.parentBox, 0, 1)
        mainLayout.addWidget(nameLabel, 1, 0)
        mainLayout.addWidget(self.nameEdit, 1, 1)
        mainLayout.addWidget(self.importWidget, 2, 0, 1, 2)
        mainLayout.addWidget(self.formulaPane, 3, 0, 1, 2)
        mainLayout.addWidget(self.buttonBox, 4, 0, 1, 2)
        mainLayout.setRowStretch(3, 1)
        self.setLayout(mainLayout)

    def accept(self) -> None:
        reply = {
            'accepted': True,
            'name': self.nameEdit.text(),
            'parent': self.parentBox.currentText(),
            'formula': self.formulaPane.editor.toPlainText(),
            'define_var': self.importWidget.shouldImport.isChecked(),
            'varname': self.importWidget.nameEdit.text()
        }
        varname = reply['varname']
        if not check_varname(varname):
            QMessageBox.critical(
                self,
                'Error',
                'Invalid variable name: %s' % varname
            )
            return
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {
            'accepted': False
        }
        super().reject()


class ImportNamesDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(
            self, parent, flags=Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle('Import Names')
        self.treeview = parent
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.importSelected = QCheckBox(_("Import selected"), self)
        self.importSelected.setCheckState(Qt.Checked)
        self.importChildren = QCheckBox(_("Import children"), self)
        self.importChildren.setCheckState(Qt.Checked)
        self.replaceExisting = QCheckBox(_("Replace existing names"), self)
        self.replaceExisting.setCheckState(Qt.Checked)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(self.importSelected)
        mainLayout.addWidget(self.importChildren)
        mainLayout.addWidget(self.replaceExisting)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    def accept(self) -> None:
        reply = {
            'accepted': True,
            'import_selected': self.importSelected.isChecked(),
            'import_children': self.importChildren.isChecked(),
            'replace_existing': self.replaceExisting.isChecked()
        }
        self.treeview.reply = reply
        super().accept()

    def reject(self) -> None:
        self.treeview.reply = {'accepted': False}
        super().reject()


if __name__ == '__main__':

    import sys
    from qtpy.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = SelectFromListDialog(
        allItems=('foo', 'bar', 'baz'),
        selectedItems=('bar',)
    )
    dialog.show()

    sys.exit(app.exec_())