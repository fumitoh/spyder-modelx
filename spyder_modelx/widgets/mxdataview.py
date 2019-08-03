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

# The source code is modified from:
# https://github.com/spyder-ide/spyder/blob/v4.0.0b1/spyder/widgets/variableexplorer/dataframeeditor.py
# See below for the original copyright notice.

# Copyright © Spyder Project Contributors
# Licensed under the terms of the New BSD License
#
# DataFrameModel is based on the class ArrayModel from array editor
# and the class DataFrameModel from the pandas project.
# Present in pandas.sandbox.qtpandas in v0.13.1
# Copyright (c) 2011-2012, Lambda Foundry, Inc.
# and PyData Development Team All rights reserved
#
# DataFrameHeaderModel and DataFrameLevelModel are based on the classes
# Header4ExtModel and Level4ExtModel from the gtabview project. The
# DataFrameModel is based on the classes ExtDataModel and ExtFrameModel from
# the same project. Also the DataFrameEditor is based in the ExtTableView.
# https://github.com/TabViewer/gtabview
# Copyright(c) 2014-2016: wave++ "Yuri D'Elia" <wavexx@thregr.org>
# Copyright(c) 2014-2015: Scott Hansen <firecat4153@gmail.com>
# Licensed under the terms of the MIT License
#


# Standard library imports
import sys, time

# Third party imports
from qtpy.compat import from_qvariant, to_qvariant
from qtpy.QtCore import (QAbstractTableModel, QModelIndex, Qt, Signal, Slot,
                         QItemSelectionModel, QEvent)
from qtpy.QtGui import QColor, QCursor
from qtpy.QtWidgets import (QApplication, QCheckBox, QDialog, QGridLayout,
                            QHBoxLayout, QInputDialog, QLineEdit, QMenu,
                            QMessageBox, QPushButton, QTableView,
                            QScrollBar, QTableWidget, QFrame,
                            QItemDelegate, QWidget, QLabel)

from pandas import DataFrame, Index, Series, MultiIndex

try:
    from pandas._libs.tslib import OutOfBoundsDatetime
except ImportError:  # For pandas version < 0.20
    from pandas.tslib import OutOfBoundsDatetime
import numpy as np

# Local imports
import spyder
from spyder.config.base import _
from spyder.config.fonts import DEFAULT_SMALL_DELTA
from spyder.config.gui import get_font, config_shortcut
from spyder.py3compat import io, is_text_string, PY2, to_text_string
if spyder.version_info > (3, 2, 5):
    from spyder.py3compat import is_type_text_string
else:
    def is_type_text_string(obj):
        """Return True if `obj` is type text string, False if it is anything else,
        like an instance of a class that extends the basestring class."""
        if PY2:
            # Python 2
            return type(obj) in [str, unicode]
        else:
            # Python 3
            return type(obj) in [str, bytes]

from spyder.utils import icon_manager as ima
from spyder.utils.qthelpers import (add_actions, create_action,
                                    keybinding, qapplication)
if spyder.version_info < (4,):
    from spyder.widgets.variableexplorer.arrayeditor import get_idx_rect
else:
    from spyder.plugins.variableexplorer.widgets.arrayeditor import get_idx_rect

from spyder.utils.qthelpers import create_plugin_layout
from spyder_modelx.widgets.mxlineedit import MxPyExprLineEdit
from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin

# Supported Numbers and complex numbers
REAL_NUMBER_TYPES = (float, int, np.int64, np.int32)
COMPLEX_NUMBER_TYPES = (complex, np.complex64, np.complex128)
# Used to convert bool intrance to false since bool('False') will return True
_bool_false = ['false', 'f', '0', '0.', '0.0', ' ']

# Default format for data frames with floats
DEFAULT_FORMAT = '%.6g'

# Limit at which dataframe is considered so large that it is loaded on demand
LARGE_SIZE = 5e5
LARGE_NROWS = 1e5
LARGE_COLS = 60
ROWS_TO_LOAD = 500

# Background colours
COLS_TO_LOAD = 40
BACKGROUND_NUMBER_MINHUE = 0.66  # hue for largest number
BACKGROUND_NUMBER_HUERANGE = 0.33  # (hue for smallest) minus (hue for largest)
BACKGROUND_NUMBER_SATURATION = 0.7
BACKGROUND_NUMBER_VALUE = 1.0
BACKGROUND_NUMBER_ALPHA = 0.6
BACKGROUND_NONNUMBER_COLOR = Qt.lightGray
BACKGROUND_INDEX_ALPHA = 0.8
BACKGROUND_STRING_ALPHA = 0.05
BACKGROUND_MISC_ALPHA = 0.3


def bool_false_check(value):
    """
    Used to convert bool entrance to false.

    Needed since any string in bool('') will return True.
    """
    if value.lower() in _bool_false:
        value = ''
    return value


def global_max(col_vals, index):
    """Returns the global maximum and minimum."""
    col_vals_without_None = [x for x in col_vals if x is not None]
    max_col, min_col = zip(*col_vals_without_None)
    return max(max_col), min(min_col)


class MxDataModel(QAbstractTableModel):
    """ DataFrame Table Model.

    Partly based in ExtDataModel and ExtFrameModel classes
    of the gtabview project.

    For more information please see:
    https://github.com/wavexx/gtabview/blob/master/gtabview/models.py
    """

    def __init__(self, dataFrame, format=DEFAULT_FORMAT, parent=None):
        QAbstractTableModel.__init__(self)
        self.dialog = parent
        self.df = dataFrame
        self.df_index = dataFrame.index.tolist()
        self.df_header = dataFrame.columns.tolist()
        self._format = format
        self.complex_intran = None

        self.total_rows = self.df.shape[0]
        self.total_cols = self.df.shape[1]
        size = self.total_rows * self.total_cols

        # Use paging when the total size, number of rows or number of
        # columns is too large
        if size > LARGE_SIZE:
            self.rows_loaded = ROWS_TO_LOAD
            self.cols_loaded = COLS_TO_LOAD
        else:
            if self.total_rows > LARGE_NROWS:
                self.rows_loaded = ROWS_TO_LOAD
            else:
                self.rows_loaded = self.total_rows
            if self.total_cols > LARGE_COLS:
                self.cols_loaded = COLS_TO_LOAD
            else:
                self.cols_loaded = self.total_cols

    def _axis(self, axis):
        """
        Return the corresponding labels taking into account the axis.

        The axis could be horizontal (0) or vertical (1).
        """
        return self.df.columns if axis == 0 else self.df.index

    def _axis_levels(self, axis):
        """
        Return the number of levels in the labels taking into account the axis.

        Get the number of levels for the columns (0) or rows (1).
        """
        ax = self._axis(axis)
        return 1 if not hasattr(ax, 'levels') else len(ax.levels)

    @property
    def shape(self):
        """Return the shape of the dataframe."""
        return self.df.shape

    @property
    def header_shape(self):
        """Return the levels for the columns and rows of the dataframe."""
        return (self._axis_levels(0), self._axis_levels(1))

    @property
    def chunk_size(self):
        """Return the max value of the dimensions of the dataframe."""
        return max(*self.shape())

    def header(self, axis, x, level=0):
        """
        Return the values of the labels for the header of columns or rows.

        The value corresponds to the header of column or row x in the
        given level.
        """
        ax = self._axis(axis)
        return ax.values[x] if not hasattr(ax, 'levels') \
            else ax.values[x][level]

    def name(self, axis, level):
        """Return the labels of the levels if any."""
        ax = self._axis(axis)
        if hasattr(ax, 'levels'):
            return ax.names[level]
        if ax.name:
            return ax.name

    def get_format(self):
        """Return current format"""
        # Avoid accessing the private attribute _format from outside
        return self._format

    def set_format(self, format):
        """Change display format"""
        self._format = format
        self.reset()

    def get_value(self, row, column):
        """Return the value of the DataFrame."""
        # To increase the performance iat is used but that requires error
        # handling, so fallback uses iloc
        try:
            value = self.df.iat[row, column]
        except OutOfBoundsDatetime:
            value = self.df.iloc[:, column].astype(str).iat[row]
        except:
            value = self.df.iloc[row, column]
        return value

    def update_df_index(self):
        """"Update the DataFrame index"""
        self.df_index = self.df.index.tolist()

    def data(self, index, role=Qt.DisplayRole):
        """Cell content"""
        if not index.isValid():
            return to_qvariant()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            column = index.column()
            row = index.row()
            value = self.get_value(row, column)
            if value is None:
                return ''
            elif np.isnan(value):
                return ''
            elif isinstance(value, float):
                try:
                    return to_qvariant(self._format % value)
                except (ValueError, TypeError):
                    # may happen if format = '%d' and value = NaN;
                    # see issue 4139
                    return to_qvariant(DEFAULT_FORMAT % value)
            elif is_type_text_string(value):
                # Don't perform any conversion on strings
                # because it leads to differences between
                # the data present in the dataframe and
                # what is shown by Spyder
                return value
            else:
                return to_qvariant(to_text_string(value))
        # elif role == Qt.BackgroundColorRole:
        #     return to_qvariant(self.get_bgcolor(index))
        elif role == Qt.FontRole:
            return to_qvariant(get_font(font_size_delta=DEFAULT_SMALL_DELTA))
        return to_qvariant()

    def sort(self, column, order=Qt.AscendingOrder):
        """Overriding sort method"""
        if self.complex_intran is not None:
            if self.complex_intran.any(axis=0).iloc[column]:
                QMessageBox.critical(self.dialog, "Error",
                                     "TypeError error: no ordering "
                                     "relation is defined for complex numbers")
                return False
        try:
            ascending = order == Qt.AscendingOrder
            if column >= 0:
                try:
                    self.df.sort_values(by=self.df.columns[column],
                                        ascending=ascending, inplace=True,
                                        kind='mergesort')
                except AttributeError:
                    # for pandas version < 0.17
                    self.df.sort(columns=self.df.columns[column],
                                 ascending=ascending, inplace=True,
                                 kind='mergesort')
                except ValueError as e:
                    # Not possible to sort on duplicate columns #5225
                    QMessageBox.critical(self.dialog, "Error",
                                         "ValueError: %s" % to_text_string(e))
                except SystemError as e:
                    # Not possible to sort on category dtypes #5361
                    QMessageBox.critical(self.dialog, "Error",
                                         "SystemError: %s" % to_text_string(e))
                self.update_df_index()
            else:
                # To sort by index
                self.df.sort_index(inplace=True, ascending=ascending)
                self.update_df_index()
        except TypeError as e:
            QMessageBox.critical(self.dialog, "Error",
                                 "TypeError error: %s" % str(e))
            return False

        self.reset()
        return True

    def flags(self, index):
        """Set flags"""
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index))

    def setData(self, index, value, role=Qt.EditRole, change_type=None):
        """Cell content change"""
        column = index.column()
        row = index.row()

        if change_type is not None:
            try:
                value = self.data(index, role=Qt.DisplayRole)
                val = from_qvariant(value, str)
                if change_type is bool:
                    val = bool_false_check(val)
                self.df.iloc[row, column] = change_type(val)
            except ValueError:
                self.df.iloc[row, column] = change_type('0')
        else:
            val = from_qvariant(value, str)
            current_value = self.get_value(row, column)
            if isinstance(current_value, (bool, np.bool_)):
                val = bool_false_check(val)
            supported_types = (bool, np.bool_) + REAL_NUMBER_TYPES
            if (isinstance(current_value, supported_types) or
                    is_text_string(current_value)):
                try:
                    self.df.iloc[row, column] = current_value.__class__(val)
                except (ValueError, OverflowError) as e:
                    QMessageBox.critical(self.dialog, "Error",
                                         str(type(e).__name__) + ": " + str(e))
                    return False
            else:
                QMessageBox.critical(self.dialog, "Error",
                                     "Editing dtype {0!s} not yet supported."
                                     .format(type(current_value).__name__))
                return False
        # self.max_min_col_update()
        self.dataChanged.emit(index, index)
        return True

    def get_data(self):
        """Return data"""
        return self.df

    def rowCount(self, index=QModelIndex()):
        """DataFrame row number"""
        if self.total_rows <= self.rows_loaded:
            return self.total_rows
        else:
            return self.rows_loaded

    def fetch_more(self, rows=False, columns=False):
        """Get more columns and/or rows."""
        if rows and self.total_rows > self.rows_loaded:
            reminder = self.total_rows - self.rows_loaded
            items_to_fetch = min(reminder, ROWS_TO_LOAD)
            self.beginInsertRows(QModelIndex(), self.rows_loaded,
                                 self.rows_loaded + items_to_fetch - 1)
            self.rows_loaded += items_to_fetch
            self.endInsertRows()
        if columns and self.total_cols > self.cols_loaded:
            reminder = self.total_cols - self.cols_loaded
            items_to_fetch = min(reminder, COLS_TO_LOAD)
            self.beginInsertColumns(QModelIndex(), self.cols_loaded,
                                    self.cols_loaded + items_to_fetch - 1)
            self.cols_loaded += items_to_fetch
            self.endInsertColumns()

    def columnCount(self, index=QModelIndex()):
        """DataFrame column number"""
        # This is done to implement series
        if len(self.df.shape) == 1:
            return 2
        elif self.total_cols <= self.cols_loaded:
            return self.total_cols
        else:
            return self.cols_loaded

    def reset(self):
        self.beginResetModel()
        self.endResetModel()


class MxDataTable(QTableView):
    """
    Data Frame view class.

    Signals
    -------
    sig_option_changed(): Raised after a sort by column.
    sig_sort_by_column(): Raised after more columns are fetched.
    sig_fetch_more_rows(): Raised after more rows are fetched.
    """
    sig_sort_by_column = Signal()
    sig_fetch_more_columns = Signal()
    sig_fetch_more_rows = Signal()

    def __init__(self, parent, model, header, hscroll, vscroll):
        """Constructor."""
        QTableView.__init__(self, parent)
        self.setModel(model)
        self.setHorizontalScrollBar(hscroll)
        self.setVerticalScrollBar(vscroll)
        self.setHorizontalScrollMode(1)
        self.setVerticalScrollMode(1)

        self.sort_old = [None]
        self.header_class = header
        self.header_class.sectionClicked.connect(self.sortByColumn)
        self.menu = self.setup_menu()
        config_shortcut(self.copy, context='variable_explorer', name='copy',
                        parent=self)
        self.horizontalScrollBar().valueChanged.connect(
            lambda val: self.load_more_data(val, columns=True))
        self.verticalScrollBar().valueChanged.connect(
            lambda val: self.load_more_data(val, rows=True))

    def load_more_data(self, value, rows=False, columns=False):
        """Load more rows and columns to display."""
        if rows and value == self.verticalScrollBar().maximum():
            self.model().fetch_more(rows=rows)
            self.sig_fetch_more_rows.emit()
        if columns and value == self.horizontalScrollBar().maximum():
            self.model().fetch_more(columns=columns)
            self.sig_fetch_more_columns.emit()

    def sortByColumn(self, index):
        """Implement a column sort."""
        if self.sort_old == [None]:
            self.header_class.setSortIndicatorShown(True)
        sort_order = self.header_class.sortIndicatorOrder()
        self.sig_sort_by_column.emit()
        if not self.model().sort(index, sort_order):
            if len(self.sort_old) != 2:
                self.header_class.setSortIndicatorShown(False)
            else:
                self.header_class.setSortIndicator(self.sort_old[0],
                                                   self.sort_old[1])
            return
        self.sort_old = [index, self.header_class.sortIndicatorOrder()]

    def contextMenuEvent(self, event):
        """Reimplement Qt method."""
        self.menu.popup(event.globalPos())
        event.accept()

    def setup_menu(self):
        """Setup context menu."""
        copy_action = create_action(self, _('Copy'),
                                    shortcut=keybinding('Copy'),
                                    icon=ima.icon('editcopy'),
                                    triggered=self.copy,
                                    context=Qt.WidgetShortcut)
        functions = ((_("To bool"), bool), (_("To complex"), complex),
                     (_("To int"), int), (_("To float"), float),
                     (_("To str"), to_text_string))
        types_in_menu = [copy_action]
        for name, func in functions:
            slot = lambda func=func: self.change_type(func)
            types_in_menu += [create_action(self, name,
                                            triggered=slot,
                                            context=Qt.WidgetShortcut)]
        menu = QMenu(self)
        add_actions(menu, types_in_menu)
        return menu

    def change_type(self, func):
        """A function that changes types of cells."""
        model = self.model()
        index_list = self.selectedIndexes()
        [model.setData(i, '', change_type=func) for i in index_list]

    @Slot()
    def copy(self):
        """Copy text to clipboard"""
        if not self.selectedIndexes():
            return
        (row_min, row_max,
         col_min, col_max) = get_idx_rect(self.selectedIndexes())
        index = header = False
        df = self.model().df
        obj = df.iloc[slice(row_min, row_max + 1),
                      slice(col_min, col_max + 1)]
        output = io.StringIO()
        obj.to_csv(output, sep='\t', index=index, header=header)
        if not PY2:
            contents = output.getvalue()
        else:
            contents = output.getvalue().decode('utf-8')
        output.close()
        clipboard = QApplication.clipboard()
        clipboard.setText(contents)


class DataFrameHeaderModel(QAbstractTableModel):
    """
    This class is the model for the header or index of the DataFrameEditor.

    Taken from gtabview project (Header4ExtModel).
    For more information please see:
    https://github.com/wavexx/gtabview/blob/master/gtabview/viewer.py
    """

    COLUMN_INDEX = -1  # Makes reference to the index of the table.

    def __init__(self, model, axis, palette):
        """
        Header constructor.

        The 'model' is the QAbstractTableModel of the dataframe, the 'axis' is
        to acknowledge if is for the header (horizontal - 0) or for the
        index (vertical - 1) and the palette is the set of colors to use.
        """
        super(DataFrameHeaderModel, self).__init__()
        self.model = model
        self.axis = axis
        self._palette = palette
        if self.axis == 0:
            self.total_cols = self.model.shape[1]
            self._shape = (self.model.header_shape[0], self.model.shape[1])
            if self.total_cols > LARGE_COLS:
                self.cols_loaded = COLS_TO_LOAD
            else:
                self.cols_loaded = self.total_cols
        else:
            self.total_rows = self.model.shape[0]
            self._shape = (self.model.shape[0], self.model.header_shape[1])
            if self.total_rows > LARGE_NROWS:
                self.rows_loaded = ROWS_TO_LOAD
            else:
                self.rows_loaded = self.total_rows

    def rowCount(self, index=None):
        """Get number of rows in the header."""
        if self.axis == 0:
            return max(1, self._shape[0])
        else:
            if self.total_rows <= self.rows_loaded:
                return self.total_rows
            else:
                return self.rows_loaded

    def columnCount(self, index=QModelIndex()):
        """DataFrame column number"""
        if self.axis == 0:
            if self.total_cols <= self.cols_loaded:
                return self.total_cols
            else:
                return self.cols_loaded
        else:
            return max(1, self._shape[1])

    def fetch_more(self, rows=False, columns=False):
        """Get more columns or rows (based on axis)."""
        if  self.axis == 1 and self.total_rows > self.rows_loaded:
            reminder = self.total_rows - self.rows_loaded
            items_to_fetch = min(reminder, ROWS_TO_LOAD)
            self.beginInsertRows(QModelIndex(), self.rows_loaded,
                                 self.rows_loaded + items_to_fetch - 1)
            self.rows_loaded += items_to_fetch
            self.endInsertRows()
        if self.axis == 0 and self.total_cols > self.cols_loaded:
            reminder = self.total_cols - self.cols_loaded
            items_to_fetch = min(reminder, COLS_TO_LOAD)
            self.beginInsertColumns(QModelIndex(), self.cols_loaded,
                                    self.cols_loaded + items_to_fetch - 1)
            self.cols_loaded += items_to_fetch
            self.endInsertColumns()

    def sort(self, column, order=Qt.AscendingOrder):
        """Overriding sort method."""
        ascending = order == Qt.AscendingOrder
        self.model.sort(self.COLUMN_INDEX, order=ascending)
        return True

    def headerData(self, section, orientation, role):
        """Get the information to put in the header."""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return Qt.AlignCenter | Qt.AlignBottom
            else:
                return Qt.AlignRight | Qt.AlignVCenter
        if role != Qt.DisplayRole and role != Qt.ToolTipRole:
            return None
        if self.axis == 1 and self._shape[1] <= 1:
            return None
        orient_axis = 0 if orientation == Qt.Horizontal else 1
        if self.model.header_shape[orient_axis] > 1:
            header = section
        else:
            header = self.model.header(self.axis, section)

            # Don't perform any conversion on strings
            # because it leads to differences between
            # the data present in the dataframe and
            # what is shown by Spyder
            if not is_type_text_string(header):
                header = to_text_string(header)

        return header

    def data(self, index, role):
        """
        Get the data for the header.

        This is used when a header has levels.
        """
        if not index.isValid() or \
           index.row() >= self._shape[0] or \
           index.column() >= self._shape[1]:
            return None
        row, col = ((index.row(), index.column()) if self.axis == 0
                    else (index.column(), index.row()))
        if role == Qt.BackgroundRole:
            prev = self.model.header(self.axis, col - 1, row) if col else None
            cur = self.model.header(self.axis, col, row)
            return self._palette.midlight() if prev != cur else None
        if role != Qt.DisplayRole:
            return None
        if self.axis == 0 and self._shape[0] <= 1:
            return None

        header = self.model.header(self.axis, col, row)

        # Don't perform any conversion on strings
        # because it leads to differences between
        # the data present in the dataframe and
        # what is shown by Spyder
        if not is_type_text_string(header):
            header = to_text_string(header)

        return header


class DataFrameLevelModel(QAbstractTableModel):
    """
    Data Frame level class.

    This class is used to represent index levels in the DataFrameEditor. When
    using MultiIndex, this model creates labels for the index/header as Index i
    for each section in the index/header

    Based on the gtabview project (Level4ExtModel).
    For more information please see:
    https://github.com/wavexx/gtabview/blob/master/gtabview/viewer.py
    """

    def __init__(self, model, palette, font):
        super(DataFrameLevelModel, self).__init__()
        self.model = model
        self._background = palette.dark().color()
        if self._background.lightness() > 127:
            self._foreground = palette.text()
        else:
            self._foreground = palette.highlightedText()
        self._palette = palette
        font.setBold(True)
        self._font = font

    def rowCount(self, index=None):
        """Get number of rows (number of levels for the header)."""
        return max(1, self.model.header_shape[0])

    def columnCount(self, index=None):
        """Get the number of columns (number of levels for the index)."""
        return max(1, self.model.header_shape[1])

    def headerData(self, section, orientation, role):
        """
        Get the text to put in the header of the levels of the indexes.

        By default it returns 'Index i', where i is the section in the index
        """
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return Qt.AlignCenter | Qt.AlignBottom
            else:
                return Qt.AlignRight | Qt.AlignVCenter
        if role != Qt.DisplayRole and role != Qt.ToolTipRole:
            return None
        if self.model.header_shape[0] <= 1 and orientation == Qt.Horizontal:
            if self.model.name(1,section):
                return self.model.name(1,section)
            return _('Index')
        elif self.model.header_shape[0] <= 1:
            return None
        elif self.model.header_shape[1] <= 1 and orientation == Qt.Vertical:
            return None
        return _('Index') + ' ' + to_text_string(section)

    def data(self, index, role):
        """Get the information of the levels."""
        if not index.isValid():
            return None
        if role == Qt.FontRole:
            return self._font
        label = ''
        if index.column() == self.model.header_shape[1] - 1:
            label = str(self.model.name(0, index.row()))
        elif index.row() == self.model.header_shape[0] - 1:
            label = str(self.model.name(1, index.column()))
        if role == Qt.DisplayRole and label:
            return label
        elif role == Qt.ForegroundRole:
            return self._foreground
        elif role == Qt.BackgroundRole:
            return self._background
        elif role == Qt.BackgroundRole:
            return self._palette.window()
        return None


class MxDataWidget(QWidget):
    """
    Dialog for displaying and editing DataFrame and related objects.

    Based on the gtabview project (ExtTableView).
    For more information please see:
    https://github.com/wavexx/gtabview/blob/master/gtabview/viewer.py

    Signals
    -------
    sig_option_changed(str, object): Raised if an option is changed.
       Arguments are name of option and its new value.
    """
    sig_option_changed = Signal(str, object)

    def __init__(self, parent=None, data=DataFrame()):
        QWidget.__init__(self, parent)
        # Destroying the C++ object right after closing the dialog box,
        # otherwise it may be garbage-collected in another QThread
        # (e.g. the editor's analysis thread in Spyder), thus leading to
        # a segmentation fault on UNIX or an application crash on Windows
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.is_series = False
        self.layout = None
        self.setup_and_check(data)

    def setup_and_check(self, data, title=''):
        """
        Setup DataFrameEditor:
        return False if data is not supported, True otherwise.
        Supported types for data are DataFrame, Series and Index.
        """
        self._selection_rec = False
        self._model = None

        self.layout = QGridLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.setWindowIcon(ima.icon('arredit'))
        if title:
            title = to_text_string(title) + " - %s" % data.__class__.__name__
        else:
            title = _("%s editor") % data.__class__.__name__
        if isinstance(data, Series):
            self.is_series = True
            data = data.to_frame()
        elif isinstance(data, Index):
            data = DataFrame(data)

        self.setWindowTitle(title)
        # self.resize(600, 500)

        self.hscroll = QScrollBar(Qt.Horizontal)
        self.vscroll = QScrollBar(Qt.Vertical)

        # Create the view for the level
        self.create_table_level()

        # Create the view for the horizontal header
        self.create_table_header()

        # Create the view for the vertical index
        self.create_table_index()

        # Create the model and view of the data
        self.dataModel = MxDataModel(data, parent=self)
        # self.dataModel.dataChanged.connect(self.save_and_close_enable)
        self.create_data_table()

        self.layout.addWidget(self.hscroll, 2, 0, 1, 2)
        self.layout.addWidget(self.vscroll, 0, 2, 2, 1)

        # autosize columns on-demand
        self._autosized_cols = set()
        self._max_autosize_ms = None
        self.dataTable.installEventFilter(self)

        avg_width = self.fontMetrics().averageCharWidth()
        self.min_trunc = avg_width * 8  # Minimum size for columns
        self.max_width = avg_width * 64  # Maximum size for columns

        self.setLayout(self.layout)
        # Make the dialog act as a window
        # self.setWindowFlags(Qt.Window)

        self.setModel(self.dataModel)
        self.resizeColumnsToContents()

        return True

    def create_table_level(self):
        """Create the QTableView that will hold the level model."""
        self.table_level = QTableView()
        self.table_level.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_level.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_level.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_level.setFrameStyle(QFrame.Plain)
        self.table_level.horizontalHeader().sectionResized.connect(
            self._index_resized)
        self.table_level.verticalHeader().sectionResized.connect(
            self._header_resized)
        # self.table_level.setItemDelegate(QItemDelegate())
        self.layout.addWidget(self.table_level, 0, 0)
        self.table_level.setContentsMargins(0, 0, 0, 0)
        self.table_level.horizontalHeader().sectionClicked.connect(
            self.sortByIndex)

    def create_table_header(self):
        """Create the QTableView that will hold the header model."""
        self.table_header = QTableView()
        self.table_header.verticalHeader().hide()
        self.table_header.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_header.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_header.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_header.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.table_header.setHorizontalScrollBar(self.hscroll)
        self.table_header.setFrameStyle(QFrame.Plain)
        self.table_header.horizontalHeader().sectionResized.connect(
            self._column_resized)
        # self.table_header.setItemDelegate(QItemDelegate())
        self.layout.addWidget(self.table_header, 0, 1)

    def create_table_index(self):
        """Create the QTableView that will hold the index model."""
        self.table_index = QTableView()
        self.table_index.horizontalHeader().hide()
        self.table_index.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_index.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_index.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_index.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table_index.setVerticalScrollBar(self.vscroll)
        self.table_index.setFrameStyle(QFrame.Plain)
        self.table_index.verticalHeader().sectionResized.connect(
            self._row_resized)
        # self.table_index.setItemDelegate(QItemDelegate())
        self.layout.addWidget(self.table_index, 1, 0)
        self.table_index.setContentsMargins(0, 0, 0, 0)

    def create_data_table(self):
        """Create the QTableView that will hold the data model."""
        self.dataTable = MxDataTable(self, self.dataModel,
                                         self.table_header.horizontalHeader(),
                                         self.hscroll, self.vscroll)
        self.dataTable.verticalHeader().hide()
        self.dataTable.horizontalHeader().hide()
        self.dataTable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dataTable.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dataTable.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.dataTable.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.dataTable.setFrameStyle(QFrame.Plain)
        # self.dataTable.setItemDelegate(QItemDelegate())
        self.layout.addWidget(self.dataTable, 1, 1)
        self.setFocusProxy(self.dataTable)
        self.dataTable.sig_sort_by_column.connect(self._sort_update)
        self.dataTable.sig_fetch_more_columns.connect(self._fetch_more_columns)
        self.dataTable.sig_fetch_more_rows.connect(self._fetch_more_rows)

    def sortByIndex(self, index):
        """Implement a Index sort."""
        self.table_level.horizontalHeader().setSortIndicatorShown(True)
        sort_order = self.table_level.horizontalHeader().sortIndicatorOrder()
        self.table_index.model().sort(index, sort_order)
        self._sort_update()

    def model(self):
        """Get the model of the dataframe."""
        return self._model

    def _column_resized(self, col, old_width, new_width):
        """Update the column width."""
        self.dataTable.setColumnWidth(col, new_width)
        self._update_layout()

    def _row_resized(self, row, old_height, new_height):
        """Update the row height."""
        self.dataTable.setRowHeight(row, new_height)
        self._update_layout()

    def _index_resized(self, col, old_width, new_width):
        """Resize the corresponding column of the index section selected."""
        self.table_index.setColumnWidth(col, new_width)
        self._update_layout()

    def _header_resized(self, row, old_height, new_height):
        """Resize the corresponding row of the header section selected."""
        self.table_header.setRowHeight(row, new_height)
        self._update_layout()

    def _update_layout(self):
        """Set the width and height of the QTableViews and hide rows."""
        h_width = max(self.table_level.verticalHeader().sizeHint().width(),
                      self.table_index.verticalHeader().sizeHint().width())
        self.table_level.verticalHeader().setFixedWidth(h_width)
        self.table_index.verticalHeader().setFixedWidth(h_width)

        last_row = self._model.header_shape[0] - 1
        if last_row < 0:
            hdr_height = self.table_level.horizontalHeader().height()
        else:

            # Check if the header shape has only one row (which display the
            # same info than the horizontal header).
            if last_row == 0:
                self.table_level.setRowHidden(0, True)
                self.table_header.setRowHidden(0, True)
            else:
                self.table_level.setRowHidden(0, False)
                self.table_header.setRowHidden(0, False)

            hdr_height = self.table_level.rowViewportPosition(last_row) + \
                         self.table_level.rowHeight(last_row) + \
                         self.table_level.horizontalHeader().height()

        self.table_header.setFixedHeight(hdr_height)
        self.table_level.setFixedHeight(hdr_height)

        last_col = self._model.header_shape[1] - 1
        if last_col < 0:
            idx_width = self.table_level.verticalHeader().width()
        else:
            idx_width = self.table_level.columnViewportPosition(last_col) + \
                        self.table_level.columnWidth(last_col) + \
                        self.table_level.verticalHeader().width()
        self.table_index.setFixedWidth(idx_width)
        self.table_level.setFixedWidth(idx_width)
        self._resizeVisibleColumnsToContents()

    def _reset_model(self, table, model):
        """Set the model in the given table."""
        old_sel_model = table.selectionModel()
        table.setModel(model)
        if old_sel_model:
            del old_sel_model

    def setAutosizeLimit(self, limit_ms):
        """Set maximum size for columns."""
        self._max_autosize_ms = limit_ms

    def setModel(self, model, relayout=True):
        """Set the model for the data, header/index and level views."""
        self._model = model
        # sel_model = self.dataTable.selectionModel()
        # sel_model.currentColumnChanged.connect(
        #     self._resizeCurrentColumnToContents)

        self._reset_model(self.dataTable, model)

        # Asociate the models (level, vertical index and horizontal header)
        # with its corresponding view.
        self._reset_model(self.table_level, DataFrameLevelModel(model,
                                                                self.palette(),
                                                                self.font()))
        self._reset_model(self.table_header, DataFrameHeaderModel(
            model,
            0,
            self.palette()))
        self._reset_model(self.table_index, DataFrameHeaderModel(
            model,
            1,
            self.palette()))

        # Needs to be called after setting all table models
        if relayout:
            self._update_layout()

    def setCurrentIndex(self, y, x):
        """Set current selection."""
        self.dataTable.selectionModel().setCurrentIndex(
            self.dataTable.model().index(y, x),
            QItemSelectionModel.ClearAndSelect)

    def _sizeHintForColumn(self, table, col, limit_ms=None):
        """Get the size hint for a given column in a table."""
        max_row = table.model().rowCount()
        lm_start = time.clock()
        lm_row = 64 if limit_ms else max_row
        max_width = 0
        for row in range(max_row):
            v = table.sizeHintForIndex(table.model().index(row, col))
            max_width = max(max_width, v.width())
            if row > lm_row:
                lm_now = time.clock()
                lm_elapsed = (lm_now - lm_start) * 1000
                if lm_elapsed >= limit_ms:
                    break
                lm_row = int((row / lm_elapsed) * limit_ms)
        return max_width

    def _resizeColumnToContents(self, header, data, col, limit_ms):
        """Resize a column by its contents."""
        hdr_width = self._sizeHintForColumn(header, col, limit_ms)
        data_width = self._sizeHintForColumn(data, col, limit_ms)
        if data_width > hdr_width:
            width = min(self.max_width, data_width)
        elif hdr_width > data_width * 2:
            width = max(min(hdr_width, self.min_trunc), min(self.max_width,
                                                            data_width))
        else:
            width = min(self.max_width, hdr_width)
        header.setColumnWidth(col, width)

    def _resizeColumnsToContents(self, header, data, limit_ms):
        """Resize all the colummns to its contents."""
        max_col = data.model().columnCount()
        if limit_ms is None:
            max_col_ms = None
        else:
            max_col_ms = limit_ms / max(1, max_col)
        for col in range(max_col):
            self._resizeColumnToContents(header, data, col, max_col_ms)

    def eventFilter(self, obj, event):
        """Override eventFilter to catch resize event."""
        if obj == self.dataTable and event.type() == QEvent.Resize:
            self._resizeVisibleColumnsToContents()
        return False

    def _resizeVisibleColumnsToContents(self):
        """Resize the columns that are in the view."""
        index_column = self.dataTable.rect().topLeft().x()
        start = col = self.dataTable.columnAt(index_column)
        width = self._model.shape[1]
        end = self.dataTable.columnAt(self.dataTable.rect().bottomRight().x())
        end = width if end == -1 else end + 1
        if self._max_autosize_ms is None:
            max_col_ms = None
        else:
            max_col_ms = self._max_autosize_ms / max(1, end - start)
        while col < end:
            resized = False
            if col not in self._autosized_cols:
                self._autosized_cols.add(col)
                resized = True
                self._resizeColumnToContents(self.table_header, self.dataTable,
                                             col, max_col_ms)
            col += 1
            if resized:
                # As we resize columns, the boundary will change
                index_column = self.dataTable.rect().bottomRight().x()
                end = self.dataTable.columnAt(index_column)
                end = width if end == -1 else end + 1
                if max_col_ms is not None:
                    max_col_ms = self._max_autosize_ms / max(1, end - start)

    def _resizeCurrentColumnToContents(self, new_index, old_index):
        """Resize the current column to its contents."""
        if new_index.column() not in self._autosized_cols:
            # Ensure the requested column is fully into view after resizing
            self._resizeVisibleColumnsToContents()
            self.dataTable.scrollTo(new_index)

    def resizeColumnsToContents(self):
        """Resize the columns to its contents."""
        self._autosized_cols = set()
        self._resizeColumnsToContents(self.table_level,
                                      self.table_index, self._max_autosize_ms)
        self._update_layout()
        self.table_level.resizeColumnsToContents()

    def change_format(self):
        """
        Ask user for display format for floats and use it.

        This function also checks whether the format is valid and emits
        `sig_option_changed`.
        """
        format, valid = QInputDialog.getText(self, _('Format'),
                                             _("Float formatting"),
                                             QLineEdit.Normal,
                                             self.dataModel.get_format())
        if valid:
            format = str(format)
            try:
                format % 1.1
            except:
                msg = _("Format ({}) is incorrect").format(format)
                QMessageBox.critical(self, _("Error"), msg)
                return
            if not format.startswith('%'):
                msg = _("Format ({}) should start with '%'").format(format)
                QMessageBox.critical(self, _("Error"), msg)
                return
            self.dataModel.set_format(format)
            self.sig_option_changed.emit('dataframe_format', format)

    def get_value(self):
        """Return modified Dataframe -- this is *not* a copy"""
        # It is import to avoid accessing Qt C++ object as it has probably
        # already been destroyed, due to the Qt.WA_DeleteOnClose attribute
        df = self.dataModel.get_data()
        if self.is_series:
            return df.iloc[:, 0]
        else:
            return df

    def _update_header_size(self):
        """Update the column width of the header."""
        column_count = self.table_header.model().columnCount()
        for index in range(0, column_count):
            if index < column_count:
                column_width = self.dataTable.columnWidth(index)
                self.table_header.setColumnWidth(index, column_width)
            else:
                break

    def _sort_update(self):
        """
        Update the model for all the QTableView objects.

        Uses the model of the dataTable as the base.
        """
        self.setModel(self.dataTable.model())

    def _fetch_more_columns(self):
        """Fetch more data for the header (columns)."""
        self.table_header.model().fetch_more()

    def _fetch_more_rows(self):
        """Fetch more data for the index (rows)."""
        self.table_index.model().fetch_more()

    def resize_to_contents(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.dataTable.resizeColumnsToContents()
        self.dataModel.fetch_more(columns=True)
        self.dataTable.resizeColumnsToContents()
        self._update_header_size()
        QApplication.restoreOverrideCursor()

    # --- mx specific ---
    def process_remote_view(self, data):

        if data is None:
            data = DataFrame() # Empty DataFrame

        self.setModel(MxDataModel(data, parent=self))
        # self.setup_and_check(data)


class MxDataViewWidget(MxToolBarMixin, QWidget):

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

        # Create main widget
        self.widget = MxDataWidget(self)

        # Main layout of this widget
        layout = create_plugin_layout(self.tools_layout, self.widget)
        self.setLayout(layout)

    def set_shellwidget(self, shellwidget):
        """Bind shellwidget instance to namespace browser"""
        self.shellwidget = shellwidget
        self.shellwidget.set_mxdataview(self.widget, self.exprbox)

    # MxToolBarMixin interface method
    def setup_toolbar(self):

        txt = _("Expression")
        if sys.platform == 'darwin':
            expr_label = QLabel("  " + txt)
        else:
            expr_label = QLabel(txt)

        if spyder.version_info < (4,):
            font = self.plugin.get_plugin_font()
        else:
            font = self.plugin.get_font()

        self.exprbox = MxPyExprLineEdit(self, font=font)

        return [expr_label, self.exprbox]

# ==============================================================================
# Tests
# ==============================================================================


def test_edit(data, title="", parent=None):
    """Test subroutine"""
    app = qapplication()  # analysis:ignore
    dlg = MxDataWidget(parent=parent)

    if dlg.setup_and_check(data, title=title):
        dlg.show()
        app.exec_()
        return dlg.get_value()
    else:
        import sys
        sys.exit(1)


def test():
    """DataFrame editor test"""
    from numpy import nan
    from pandas.util.testing import assert_frame_equal, assert_series_equal

    df1 = DataFrame([
        [True, "bool"],
        [1 + 1j, "complex"],
        ['test', "string"],
        [1.11, "float"],
        [1, "int"],
        [np.random.rand(3, 3), "Unkown type"],
        ["Large value", 100],
        ["áéí", "unicode"]
    ],
        index=['a', 'b', nan, nan, nan, 'c',
               "Test global max", 'd'],
        columns=[nan, 'Type'])
    out = test_edit(df1)
    assert_frame_equal(df1, out)

    result = Series([True, "bool"], index=[nan, 'Type'], name='a')
    out = test_edit(df1.iloc[0])
    assert_series_equal(result, out)

    df1 = DataFrame(np.random.rand(100100, 10))
    out = test_edit(df1)
    assert_frame_equal(out, df1)

    series = Series(np.arange(10), name=0)
    out = test_edit(series)
    assert_series_equal(series, out)


def sample_multindseries():

    arrays = [['bar', 'bar', 'baz', 'baz', 'foo', 'foo', 'qux', 'qux'],
              ['one', 'two', 'one', 'two', 'one', 'two', 'one', 'two']]

    tuples = list(zip(*arrays))
    index = MultiIndex.from_tuples(tuples, names=['first', 'second'])
    return Series(np.random.randn(8), index=index)


if __name__ == '__main__':
    test_edit(sample_multindseries())
