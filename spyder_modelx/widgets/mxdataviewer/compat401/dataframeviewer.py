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
if spyder.version_info > (4,):
    from spyder.config.manager import CONF
    config_shortcut = CONF.config_shortcut
else:
    from spyder.config.gui import config_shortcut
from spyder.config.gui import get_font
from spyder.py3compat import io, is_text_string, PY2, to_text_string
if spyder.version_info > (4,):
    from spyder.py3compat import perf_counter
else:
    from time import perf_counter
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

if spyder.version_info > (4,):
    from spyder.plugins.variableexplorer.widgets.arrayeditor import get_idx_rect
else:
    from spyder.widgets.variableexplorer.arrayeditor import get_idx_rect

from spyder.plugins.variableexplorer.widgets.dataframeeditor import (
    DataFrameModel, DataFrameView, DataFrameHeaderModel, DataFrameLevelModel)

from spyder.utils.qthelpers import create_plugin_layout

from spyder_modelx.widgets.mxlineedit import MxPyExprLineEdit
from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin


class MxDataFrameViewer(QWidget):
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

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        # Destroying the C++ object right after closing the dialog box,
        # otherwise it may be garbage-collected in another QThread
        # (e.g. the editor's analysis thread in Spyder), thus leading to
        # a segmentation fault on UNIX or an application crash on Windows
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.is_series = False
        self.layout = None

        # if not data:
        #     data = DataFrame()
        # self.setup_and_check(data) # mx change

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
        # self.resize(600, 500)     # mx change

        self.hscroll = QScrollBar(Qt.Horizontal)
        self.vscroll = QScrollBar(Qt.Vertical)

        # Create the view for the level
        self.create_table_level()

        # Create the view for the horizontal header
        self.create_table_header()

        # Create the view for the vertical index
        self.create_table_index()

        # Create the model and view of the data
        self.dataModel = DataFrameModel(data, parent=self)
        # self.dataModel.dataChanged.connect(self.save_and_close_enable) # mx change
        self.create_data_table()

        self.layout.addWidget(self.hscroll, 2, 0, 1, 2)
        self.layout.addWidget(self.vscroll, 0, 2, 2, 1)

        # autosize columns on-demand
        self._autosized_cols = set()
        # Set limit time to calculate column sizeHint to 300ms,
        # See spyder-ide/spyder#11060
        self._max_autosize_ms = 300
        self.dataTable.installEventFilter(self)

        avg_width = self.fontMetrics().averageCharWidth()
        self.min_trunc = avg_width * 12  # Minimum size for columns
        self.max_width = avg_width * 64  # Maximum size for columns

        self.setLayout(self.layout)
        self.setMinimumSize(400, 300)
        # Make the dialog act as a window
        # self.setWindowFlags(Qt.Window)    # mx change
        btn_layout = QHBoxLayout()

        btn = QPushButton(_("Format"))
        # disable format button for int type
        btn_layout.addWidget(btn)
        btn.clicked.connect(self.change_format)
        btn = QPushButton(_('Resize'))
        btn_layout.addWidget(btn)
        btn.clicked.connect(self.resize_to_contents)

        bgcolor = QCheckBox(_('Background color'))
        bgcolor.setChecked(self.dataModel.bgcolor_enabled)
        bgcolor.setEnabled(self.dataModel.bgcolor_enabled)
        bgcolor.stateChanged.connect(self.change_bgcolor_enable)
        btn_layout.addWidget(bgcolor)

        self.bgcolor_global = QCheckBox(_('Column min/max'))
        self.bgcolor_global.setChecked(self.dataModel.colum_avg_enabled)
        self.bgcolor_global.setEnabled(not self.is_series and
                                       self.dataModel.bgcolor_enabled)
        self.bgcolor_global.stateChanged.connect(self.dataModel.colum_avg)
        btn_layout.addWidget(self.bgcolor_global)

        btn_layout.addStretch()

        # mx change

        # self.btn_save_and_close = QPushButton(_('Save and Close'))
        # self.btn_save_and_close.setDisabled(True)
        # self.btn_save_and_close.clicked.connect(self.accept)
        # btn_layout.addWidget(self.btn_save_and_close)
        #
        # self.btn_close = QPushButton(_('Close'))
        # self.btn_close.setAutoDefault(True)
        # self.btn_close.setDefault(True)
        # self.btn_close.clicked.connect(self.reject)
        # btn_layout.addWidget(self.btn_close)

        btn_layout.setContentsMargins(4, 4, 4, 4)
        self.layout.addLayout(btn_layout, 4, 0, 1, 2)
        self.setModel(self.dataModel)
        self.resizeColumnsToContents()

        return True

    @Slot(QModelIndex, QModelIndex)
    def save_and_close_enable(self, top_left, bottom_right):
        """Handle the data change event to enable the save and close button."""
        self.btn_save_and_close.setEnabled(True)
        self.btn_save_and_close.setAutoDefault(True)
        self.btn_save_and_close.setDefault(True)

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
        # self.table_level.setItemDelegate(QItemDelegate()) # mx change
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
        # self.table_header.setItemDelegate(QItemDelegate())    # mx change
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
        # self.table_index.setItemDelegate(QItemDelegate()) # mx change
        self.layout.addWidget(self.table_index, 1, 0)
        self.table_index.setContentsMargins(0, 0, 0, 0)

    def create_data_table(self):
        """Create the QTableView that will hold the data model."""
        self.dataTable = DataFrameView(self, self.dataModel,
                                       self.table_header.horizontalHeader(),
                                       self.hscroll, self.vscroll)
        self.dataTable.verticalHeader().hide()
        self.dataTable.horizontalHeader().hide()
        self.dataTable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dataTable.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dataTable.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.dataTable.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.dataTable.setFrameStyle(QFrame.Plain)
        # self.dataTable.setItemDelegate(QItemDelegate())   # mx change
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
            hdr_height = self.table_level.rowViewportPosition(last_row) + \
                         self.table_level.rowHeight(last_row) + \
                         self.table_level.horizontalHeader().height()
            # Check if the header shape has only one row (which display the
            # same info than the horizontal header).
            if last_row == 0:
                self.table_level.setRowHidden(0, True)
                self.table_header.setRowHidden(0, True)
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

    def setAutosizeLimitTime(self, limit_ms):
        """Set maximum time to calculate size hint for columns."""
        self._max_autosize_ms = limit_ms

    def setModel(self, model, relayout=True):
        """Set the model for the data, header/index and level views."""
        self._model = model

        # mx change
        # sel_model = self.dataTable.selectionModel()
        # sel_model.currentColumnChanged.connect(
        #     self._resizeCurrentColumnToContents)

        # mx change
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
        lm_start = perf_counter()
        lm_row = 64 if limit_ms else max_row
        max_width = self.min_trunc
        for row in range(max_row):
            v = table.sizeHintForIndex(table.model().index(row, col))
            max_width = max(max_width, v.width())
            if row > lm_row:
                lm_now = perf_counter()
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
            width = max(min(self.max_width, hdr_width), self.min_trunc)
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

    def change_bgcolor_enable(self, state):
        """
        This is implementet so column min/max is only active when bgcolor is
        """
        self.dataModel.bgcolor(state)
        self.bgcolor_global.setEnabled(not self.is_series and state > 0)

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
        self.table_header.resizeColumnsToContents()
        column_count = self.table_header.model().columnCount()
        for index in range(0, column_count):
            if index < column_count:
                column_width = self.dataTable.columnWidth(index)
                header_width = self.table_header.columnWidth(index)
                if column_width > header_width:
                    self.table_header.setColumnWidth(index, column_width)
                else:
                    self.dataTable.setColumnWidth(index, header_width)
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

    # # mx change
    # def process_remote_view(self, data):
    #
    #     if data is None:
    #         data = DataFrame() # Empty DataFrame
    #
    #     self.setModel(DataFrameModel(data, parent=self))
    #     # self.setup_and_check(data)


# ==============================================================================
# Tests
# ==============================================================================


def test_edit(data, title="", parent=None):
    """Test subroutine"""
    app = qapplication()  # analysis:ignore
    dlg = MxDataFrameViewer(parent=parent)

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
