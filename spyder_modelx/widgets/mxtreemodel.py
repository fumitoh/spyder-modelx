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

import itertools
import enum
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt

class TreeCol(enum.IntEnum):

    OJBTYPE = 1
    PARAM = 2
    IS_DERIVED = 3
    LEN = 4
    VAL = 5


class BaseItem(object):
    """Base Item class for all tree item classes."""

    def __init__(self, data, parent=None):

        self.parentItem = parent
        self.itemData = None
        self.childItems = []
        self.updateData(data)

    def updateData(self, data):
        if self.itemData != data:
            self.itemData = data
            self.updateChild()
        else:
            self.itemData = data

    def updateChild(self):
        raise NotImplementedError

    def changeParent(self, parent):
        self.parentItem = parent

    def appendChild(self, item):
        item.changeParent(self)
        self.childItems.append(item)

    def insertChild(self, index, item):
        item.changeParent(self)
        self.childItems.insert(index, item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 5

    def data(self, column):

        if column == 0:
            return self.itemData['repr']
        elif column == TreeCol.OJBTYPE:
            return self.getType()
        elif column == TreeCol.PARAM:
            return self.getParams()
        elif column == TreeCol.IS_DERIVED:
            if '_is_derived' in self.itemData:
                return str(self.itemData['_is_derived'])
            else:
                return None
        elif column == TreeCol.LEN:
            if '__len__' in self.itemData:
                l = self.itemData['__len__']
                return str(l) if l else ""      # Hide 0
            else:
                return None
        else:
            raise IndexError

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    def getType(self):
        return self.itemData.get('type', '')

    def getParams(self):
        raise NotImplementedError

    def __getattr__(self, item):
        return self.itemData[item]


class InterfaceItem(BaseItem):
    """Object item, such as Model, Space, Cells"""

    @property
    def objid(self):
        return self.itemData['id']

    def __eq__(self, other):
        if isinstance(other, InterfaceItem):
            return self.objid == other.objid
        else:
            return False

    def __hash__(self):
        return hash(self.objid)


class ViewItem(BaseItem):

    @property
    def attrid(self):
        return self.getType()

    def __eq__(self, other):
        if isinstance(other, ViewItem):
            return (self.parent() == other.parent()
                    and self.attrid == other.attrid)

    def __hash__(self):
        return hash((self.parent().objid, self.attrid))


class SpaceContainerItem(InterfaceItem):
    """Base Item class for Models and Spaces which inherit SpaceContainer."""

    def updateChild(self):
        raise NotImplementedError

    def getSpaceContainerList(self):
        result = []
        result.append(self.itemData['fullname'])
        for child in self.childItems:
            if isinstance(child, SpaceContainerItem):
                result.extend(child.getSpaceContainerList())
        return result

    def getChildSpaceList(self):
        result = []
        for child in self.childItems:
            if isinstance(child, SpaceContainerItem):
                result.append(child.itemData['namedid'])
                result.extend(child.getChildSpaceList())
        return result


class ModelItem(SpaceContainerItem):
    """Item class for a Model (root item)"""
    def __init__(self, data):
        super(ModelItem, self).__init__(data, parent=None)

    def updateChild(self):
        data = self.itemData
        self.childItems.clear()
        self.childItems.extend(SpaceItem(space, self)
                               for space in data['spaces']['items'].values())
        self.childItems.extend(RefItem(ref, self)
                               for ref in data['refs']['items'].values())

    def getParams(self):
        return ''


class SpaceItem(SpaceContainerItem):
    """Item class for Space objects."""
    def updateChild(self):
        self.childItems.clear()
        dynspaces = self.itemData['_named_itemspaces']['items']
        if len(dynspaces) > 0:
            self.childItems.append(ItemSpaceMapItem(dynspaces, self))

        for space in self.itemData['named_spaces']['items'].values():
            self.childItems.append(UserSpaceItem(space, self))

        cellsmap = self.itemData['cells']['items']
        for cells in cellsmap.values():
            self.childItems.append(CellsItem(cells, self))

        refview = self.itemData['refs']['items']
        for ref in refview.values():
            self.childItems.append(RefItem(ref, self))


    def getParams(self):
        if 'argvalues' in self.itemData:
            args = self.itemData['argvalues']
            if args is None:
                return ''
            else:
                return args
        else:
            return ''

class UserSpaceItem(SpaceItem): pass

class ItemSpaceItem(SpaceItem): pass


class ItemSpaceMapItem(ViewItem):
    """Item class for parent nodes of dynamic spaces of a space."""
    def updateChild(self):
        self.childItems.clear()
        for space in self.itemData.values():
            self.childItems.append(ItemSpaceItem(space, self))

    def data(self, column):
        if column == 0:
            return 'ItemSpaces'
        else:
            return BaseItem.data(self, column)

    def getParams(self):
        params = self.parent().itemData['parameters']
        return ", ".join(params) if params else ""

class CellsItem(InterfaceItem):
    """Item class for cells objects."""
    def updateChild(self):
        pass

    def getParams(self):
        params = self.itemData['parameters']
        return ", ".join(params) if params else ""


class RefItem(InterfaceItem):
    """Item class for references."""
    def updateChild(self):
        pass

    def getType(self):
        return "Ref/" + self.itemData["value_type"]

    def getParams(self):
        return ''


class MxTreeModel(QAbstractItemModel):

    def __init__(self, item, parent=None):
        super(MxTreeModel, self).__init__(parent)
        self.rootItem = item

    def updateRoot(self, item):
        newmodel = item
        if self.updateItem(QModelIndex(), newmodel):
            # Refresh view when data changed
            # https://www.qtcentre.org/threads/48230-QTreeView-How-to-refresh-the-view?p=270537#post270537
            self.dataChanged.emit(QModelIndex(), QModelIndex())

    def getItem(self, index):
        if not index.isValid():
            return self.rootItem
        else:
            return index.internalPointer()

    def updateItem(self, index, newitem, recursive=True):

        updated = False

        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()

        if item.itemData != newitem.itemData:

            updated = True

            item.itemData = newitem.itemData
            # self.dataChanged.emit(index, index)
            delItems = set(item.childItems) - set(newitem.childItems)

            if delItems:
                delRows = sorted([item.row() for item in delItems])
                # https://stackoverflow.com/questions/10420464/group-list-of-ints-by-continuous-sequence
                delRows = [list(g) for _, g in itertools.groupby(
                    delRows, key=lambda n, c=itertools.count(): n-next(c))]

                # Example:
                # delRows = [2,3,4,7,8,9]
                # key(n): delRows -> [2, 2, 2, 4, 4, 4]
                # delRows = [[2,3,4],[7,8,9]]

                shift = 0
                for rows in delRows:
                    self.removeRows(rows[0]-shift, len(rows), index)
                    shift += len(rows)

            addItems = set(newitem.childItems) - set(item.childItems)

            if addItems:
                addRows = sorted([item.row() for item in addItems])
                addRows = [list(g) for _, g in itertools.groupby(
                    addRows, key=lambda n, c=itertools.count(): n-next(c))]

                for rows in addRows:
                    self.insertRows(rows, newitem, index)

            self.reorderChild(index, newitem)

            if recursive:
                for row, child in enumerate(item.childItems):
                    child_index = self.index(row, 0, index)
                    self.updateItem(child_index, newitem.childItems[row])

        return updated

    def insertRows(self, rows, newitem, parent):
        # Signature is different from the base method.
        item = self.getItem(parent)
        self.beginInsertRows(parent, rows[0], rows[-1])

        for row in rows:
            item.insertChild(row, newitem.childItems[row])

        self.endInsertRows()

    def removeRows(self, position, rows, parent=QModelIndex()):

        item = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)

        # for row in range(position, position + rows):
        while rows > 0:
            item.childItems.pop(position)
            rows -= 1

        self.endRemoveRows()

    def reorderChild(self, parent, newitem):
        """Reorder a list to match target by moving a sequence at a time.

        Written for QtAbstractItemModel.moveRows.
        """
        source = self.getItem(parent).childItems
        target = newitem.childItems

        i = 0
        while i < len(source):

            if source[i] == target[i]:
                i += 1
                continue
            else:
                i0 = i
                j0 = source.index(target[i0])
                j = j0 + 1
                while j < len(source):
                    if source[j] == target[j - j0 + i0]:
                        j += 1
                        continue
                    else:
                        break
                self.moveRows(parent, i0, j0, j - j0)
                i += j - j0

    def moveRows(self, parent, index_to, index_from, length):
        """Move a sub sequence in a list

        index_to must be smaller than index_from
        """
        source = self.getItem(parent).childItems

        self.beginMoveRows(parent, index_from, index_from + length - 1,
                           parent, index_to)

        sublist = [source.pop(index_from) for _ in range(length)]

        for _ in range(length):
            source.insert(index_to, sublist.pop())

        self.endMoveRows()

    @property
    def modelid(self):
        if self.rootItem:
            return self.rootItem.objid
        else:
            return None

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            # TODO: Refactor hard-coding column indexes
            if section == 0:
                return 'Objects'
            elif section == 1:
                return 'Type'
            elif section == 2:
                return 'Parameters'
            elif section == 3:
                return 'Is Derived'
            elif section == 4:
                return 'No. Data'

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is None or parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()




