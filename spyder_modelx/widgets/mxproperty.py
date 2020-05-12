
from collections import namedtuple
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import (
    QTableView, QApplication, QTreeView, QStyledItemDelegate,
    QMessageBox, QLineEdit, QWidget, QVBoxLayout, QScrollArea
)
import spyder
from spyder_modelx.widgets.mxcodeeditor import BaseCodePane, MxCodeEditor
from spyder_modelx.utility.formula import is_funcdef_or_lambda

COLS = COL_TITLE, COL_VALUE = range(2)
COL_HEADER = "Property", "Value"

Property = namedtuple(
    "Property",
    ["attr", "title", "is_editable", "editor", "is_multiple", "to_text"]
)

property_defaults = (False, None, False, None)


class FormulaEditor(MxCodeEditor):

    def __init__(self, parent):
        self.init_finished = False
        MxCodeEditor.__init__(self, parent)

        self.text_before_focus = None
        self.init_finished = True

    def focusInEvent(self, event):
        """Reimplemented to handle focus"""
        self.text_before_focus = self.toPlainText()
        super().focusInEvent(event)


class BasePropertyData:

    properties = []
    visibleIndexes = []

    def __init__(self, data):
        self.data = data

    @property
    def size(self):
        return len(self.visibleIndexes)

    def is_multiple(self, row):
        return self._get_property(row).is_multiple

    def get_value(self, row):
        if self.has_value(row):
            attr = self._get_property(row).attr
            return self.data[attr]
        else:
            return ""

    def get_text(self, row):
        to_text = self._get_property(row).to_text
        if to_text:
            return to_text(self.get_value(row))
        else:
            return str(self.get_value(row))

    def has_value(self, row):
        attr = self._get_property(row).attr
        return attr in self.data

    def get_title(self, row):
        return self._get_property(row).title

    def _get_property(self, row):
        return self.properties[self.visibleIndexes[row]]

    def __getitem__(self, item):
        return self.data[item]

    def __contains__(self, item):
        return item in self.data

    def __getattr__(self, item):
        props = {prop.attr: prop for prop in self.properties}
        if item in props:
            return props[item]
        else:
            raise AttributeError


class SpacePropertyData(BasePropertyData):

    properties = [
        Property(*(("type", "Type") + property_defaults)),
        Property(*("repr", "Name") + property_defaults),
        Property(*("_evalrepr", "Full Name") + property_defaults),
        Property("parameters", "Parameters", False, None, False,
                 lambda args: ", ".join(args)),
        Property("bases", "Base Spaces", False, None, False,
                 lambda args: ", ".join(args)),
        Property(*(("allow_none", "Allow None") + property_defaults)),
        Property("formula", "Formula", False, None, False, None)
    ]
    visibleIndexes = list(range(len(properties)))[:-1]


class ItemSpacePropertyData(BasePropertyData):

    properties = [
        Property(*(("type", "Type") + property_defaults)),
        Property(*(("repr", "Parent[Args]") + property_defaults)),
        Property(*(("_evalrepr", "Full Name") + property_defaults)),
        Property("bases", "Base Spaces", False, None, False,
                 lambda args: ", ".join(args))
    ]
    visibleIndexes = list(range(len(properties)))


class CellsPropertyData(BasePropertyData):

    properties = [
        Property(*(("type", "Type") + property_defaults)),
        Property(*(("repr", "Name") + property_defaults)),
        Property(*(("_evalrepr", "Full Name") + property_defaults)),
        Property("parameters", "Parameters", False, None, False,
                 lambda args: ", ".join(args)),
        Property(*(("allow_none", "Allow None") + property_defaults)),
        Property("formula", "Formula", True, None, False, None)
    ]
    visibleIndexes = list(range(len(properties)))[:-1]


class ReferencePropertyData(BasePropertyData):

    properties = [
        Property(*(("type", "Type") + property_defaults)),
        Property(*(("repr", "Name") + property_defaults)),
        Property(*(("_evalrepr", "Full Name") + property_defaults)),
        Property(*(("value_type", "Value Type") + property_defaults))
    ]
    visibleIndexes = list(range(len(properties)))


PropertyDataTypes = {
    "Space": SpacePropertyData,
    "Cells": CellsPropertyData,
    "UserSpace": SpacePropertyData,
    "ItemSpace": ItemSpacePropertyData,
    "Reference": ReferencePropertyData
}


class MxPropertyItemDelegate(QStyledItemDelegate):

    def createEditor(self, parent, styleOption, index):
        editor = QLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, QLineEdit):
            txt = index.model().data(index, Qt.DisplayRole)
            editor.setText(txt)
        # elif isinstance(editor, QDateTimeEdit):
        #     editor.setDate(QDate.fromString(
        #         index.model().data(index, Qt.EditRole), self.parent().currentDateFormat))


class MxPropertyView(QTreeView):

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self._parent = parent
        # self.formulaPane = parent.formulaPane
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(False)
        # self.doubleClicked.connect(self.openEditor)
        self.setItemDelegate(MxPropertyItemDelegate(self))
        self.setContentsMargins(0, 0, 0, 0)

    # TODO: Implement
    def openEditor(self, index):
        data = index.internalPointer()
        if not data._get_property(index.row()).is_editable:
            QMessageBox.warning(self, "Abc", "def")


class MxPropertyModel(QAbstractItemModel):

    def __init__(self, parent=None, data=None):
        super(MxPropertyModel, self).__init__(parent)
        self.formulaPane = parent.formulaPane
        self.resetPropData(data)

    def resetPropData(self, data):
        klass = PropertyDataTypes[data["type"]]
        self.beginResetModel()
        self.propertyData = klass(data)
        self.endResetModel()
        if hasattr(self.propertyData, "formula"):
            if self.propertyData["formula"]:
                s = self.propertyData["formula"]["source"]
            else:
                s = ""
            self.formulaPane.editor.setReadOnly(
                not self.propertyData.formula.is_editable
            )
        else:
            s = ""
            self.formulaPane.editor.setReadOnly(True)
        self.formulaPane.editor.set_text(s)

    def rowCount(self, parent):     # pure virtual
        if not parent.isValid():
            return self.propertyData.size
        else:
            return 0

    def columnCount(self, parent):  # pure virtual
        return len(COLS)

    def index(self, row, column, parent):      # pure virtual
        if self.hasIndex(row, column, parent):
            return self.createIndex(row, column, self.propertyData)
        else:
            return QModelIndex()

    def parent(self, index):        # pure virtual
        return QModelIndex()

    def data(self, index, role):    # pure virtual
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        data = index.internalPointer()
        row = index.row()
        col = index.column()

        if col:
            return data.get_text(row)
        else:
            return data.get_title(row)

    def flags(self, index):         # virtual
        if not index.isValid():
            return Qt.NoItemFlags
        else:
            row, col = index.row(), index.column()
            data = index.internalPointer()
            if col == COL_TITLE:
                return Qt.ItemIsEnabled     # | Qt.ItemIsSelectable

            elif col == COL_VALUE:
                if data._get_property(row).is_editable:
                    return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
                else:
                    return Qt.ItemIsEnabled | Qt.ItemIsSelectable
            else:
                raise RuntimeError("must not happen")

        # https://forum.qt.io/topic/99175/qtreeview-qt-itemiseditable-and-double-clicking-issues/3
        # return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, column, orientation, role):       # virtual

        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if column < len(COLS):
                return COL_HEADER[column]

        return None


class MxPropertyWidget(QScrollArea):

    def __init__(self, parent):
        super().__init__(parent)
        self.shell = None   # To be set by MxShellWidget
        self.plugin = parent.plugin
        self._parent = parent
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = view = MxPropertyView(self)
        # view.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        self.setWidgetResizable(True)
        # self.setContentsMargins(0, 0, 0, 0)

        self.formulaPane = BaseCodePane(self, title='Formula',
                                       editor_type=FormulaEditor)

        if spyder.version_info < (4,):
            self.formulaPane.editor.focus_changed.connect(self.formula_updated)
        else:
            self.formulaPane.editor.sig_focus_changed.connect(self.formula_updated)

        layout.addWidget(self.formulaPane)
        layout.setStretch(1, 1)
        self.setLayout(layout)

    def process_remote_view(self, data):
        if data:
            self._parent.raise_tab(self)
            model = self.view.model()
            if model:
                model.resetPropData(data)
            else:
                self.view.setModel(MxPropertyModel(parent=self, data=data))
        else:
            self.view.setModel(None)
            self.formulaPane.editor.set_text("")
            self.formulaPane.editor.setReadOnly(True)

    def formula_updated(self):
        if not self.view.model():
            return

        editor = self.formulaPane.editor
        text = editor.toPlainText()
        if editor.text_before_focus != text:
            data = self.view.model().propertyData
            if is_funcdef_or_lambda(text):
                self.shell.set_formula(data["fullname"], text)
                self.shell.update_mxproperty(data["fullname"])
            else:
                QMessageBox.warning(
                    self, 'Error',
                    'Invalid formula definition or lambda expression')

                self.shell.update_mxproperty(data["fullname"])


if __name__ == '__main__':

    import sys
    import modelx as mx

    model = mx.read_model(r"C:\Users\fumito\Downloads\tempmodel")

    attrs = model.SpaceB._baseattrs
    data = SpacePropertyData(attrs)
    app = QApplication(sys.argv)

    view = MxPropertyView()
    # view.setItemDelegate(MxPropertyItemDelegate(view))

    qmodel = MxPropertyModel(data=data)

    view.setModel(qmodel)
    view.show()

    sys.exit(app.exec_())


