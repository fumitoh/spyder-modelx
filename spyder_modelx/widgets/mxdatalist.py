
from collections import namedtuple
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt, Slot, QMetaMethod
from qtpy.QtWidgets import (
    QTableView, QApplication, QTreeView, QStyledItemDelegate,
    QMessageBox, QLineEdit, QWidget, QVBoxLayout, QScrollArea,
    QDialogButtonBox, QPushButton, QHBoxLayout, QLabel, QSplitter
)

COLS = COL_TITLE, COL_VALUE = range(2)
COL_HEADER = "Property", "Value"

# ------ ListItem classes -----------------------------------------------------


class BaseListItem:

    child_key = None
    child_class = None

    def __init__(self, parent, index, data):

        self.parent = parent
        self.index = index
        self.child_items = []
        self.attrs = {}

        for key, val in data.items():
            if key == self.child_key:
                for i, child_data in enumerate(val):
                    self.child_items.append(
                        self.child_class(self, i, child_data))
            else:
                self.attrs[key] = val

    def get_display_role(self, column):
        raise NotImplementedError


class ValueListItem(BaseListItem):

    child_key = "values"

    def get_display_role(self, column):
        return None


class ValueItem(BaseListItem):

    child_key = "refs"

    def get_display_role(self, column):
        if column == 0:
            return self.attrs["value"]
        elif column == 1:
            spec = self.attrs["spec"]
            return spec["path"] if spec else None
        else:
            return None


class RefItem(BaseListItem):

    child_key = None
    child_class = None

    def get_display_role(self, column):
        if column == 0:        # ref name with parents
            return ".".join(self.attrs["fullname"].split(".")[1:])
        else:
            return None


ValueListItem.child_class = ValueItem
ValueItem.child_class = RefItem


# ------ MxDataList Model and View --------------------------------------------


class MxDataListView(QTreeView):

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self._parent = parent
        # self.formulaPane = parent.formulaPane
        # self.setRootIsDecorated(False)
        # self.setAlternatingRowColors(False)
        # self.doubleClicked.connect(self.openEditor)
        # self.setItemDelegate(MxPropertyItemDelegate(self))
        # self.setContentsMargins(0, 0, 0, 0)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        if current.isValid():
            item = current.internalPointer()
            if isinstance(item, ValueItem) and item.attrs["spec"]:
                self.parent().update_dataattrs(item)
            else:
                self.parent().update_dataattrs(None)


class MxDataListModel(QAbstractItemModel):
    """
        value      | spec.path      # 1st level
         |
         +-ref                      # 2nd level
    """

    def __init__(self, parent=None, data=None):
        super(MxDataListModel, self).__init__(parent)
        self.resetDataList(data)

    def resetDataList(self, data):
        self.beginResetModel()
        self.value_info = ValueListItem(
            parent=None,
            index=0,
            data={"values": data}
        )
        self.endResetModel()

    def _get_item(self, index):

        if index.isValid():
            return index.internalPointer()
        else:
            return self.value_info

    def rowCount(self, parent):     # pure virtual
        return len(self._get_item(parent).child_items)

    def columnCount(self, parent):             # pure virtual
        return 2

    def index(self, row, column, parent):      # pure virtual

        if self.hasIndex(row, column, parent):
            parent_item = self._get_item(parent)
            return self.createIndex(row, column, parent_item.child_items[row])

        else:
            return QModelIndex()

    def parent(self, index):        # pure virtual

        parent_item = self._get_item(index).parent

        if isinstance(parent_item, ValueListItem):
            return QModelIndex()
        else:
            return self.createIndex(parent_item.index, 0, parent_item)

    def data(self, index, role):    # pure virtual

        if role != Qt.DisplayRole:
            return None

        row = index.row()
        col = index.column()

        item = self._get_item(index)
        return item.get_display_role(col)

    def flags(self, index):                                # virtual
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, column, orientation, role):       # virtual

        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if column == 0:
                return "Value/Name"
            else:
                return "Path"
        return None

# ------ Main widget in the tab -----------------------------------------------


class MxDataListWidget(QSplitter):

    def __init__(self, parent, orientation):
        super().__init__(parent, orientation=orientation)
        self.shell = None   # To be set by MxShellWidget
        self.plugin = parent.plugin
        self._parent = parent
        self.datalist = MxDataListView(self)
        self.dataattrs = MxDataAttrsView(self)

    def process_remote_view(self, data):
        if data:
            model = self.datalist.model()
            if model:
                model.resetDataList(data)
            else:
                self.datalist.setModel(
                    MxDataListModel(parent=self, data=data))
        else:
            self.datalist.setModel(None)

    def update_dataattrs(self, item):
        if item:
            model = self.dataattrs.model()
            if model:
                model.resetItemData(item)
            else:
                self.dataattrs.setModel(
                    MxDataAttrsModel(parent=self, item=item))
        else:
            self.dataattrs.setModel(None)

# ------ MxDataAttrs Model and View -------------------------------------------


class MxDataAttrsView(QTreeView):

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self._parent = parent
        # self.formulaPane = parent.formulaPane
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(False)
        # self.doubleClicked.connect(self.openEditor)
        # self.setItemDelegate(MxPropertyItemDelegate(self))
        self.setContentsMargins(0, 0, 0, 0)


class MxDataAttrsModel(QAbstractItemModel):

    def __init__(self, parent=None, item=None):
        super(MxDataAttrsModel, self).__init__(parent)
        self.resetItemData(item)

    def resetItemData(self, item):
        self.beginResetModel()
        self.spec = {}
        for k, v in item.attrs["spec"].items():
            if isinstance(v, str):
                self.spec[k] = v
        self.endResetModel()

    def rowCount(self, parent):     # pure virtual
        if not parent.isValid():
            return len(self.spec)
        else:
            return 0

    def columnCount(self, parent):  # pure virtual
        return 2

    def index(self, row, column, parent):      # pure virtual
        if self.hasIndex(row, column, parent):
            return self.createIndex(row, column, self.spec)
        else:
            return QModelIndex()

    def parent(self, index):        # pure virtual
        return QModelIndex()

    def data(self, index, role):    # pure virtual
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        row = index.row()
        col = index.column()

        for i, key in enumerate(self.spec):
            if i == row:
                break

        if col == 0:
            return key
        elif col == 1:
            return self.spec[key]
        else:
            raise ValueError("must not happen")

    def flags(self, index):                                # virtual
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, column, orientation, role):       # virtual

        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if column == 0:
                return "Parameter"
            elif column == 1:
                return "Value"

        return None




