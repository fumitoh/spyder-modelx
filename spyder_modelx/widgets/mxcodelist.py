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

import sys
from textwrap import dedent

# Third party imports
from qtpy.QtCore import (Qt, Signal, Slot,
                         QAbstractListModel)

from qtpy.QtWidgets import (QLabel, QVBoxLayout, QWidget,
                            QMainWindow, QScrollArea,
                            QAbstractItemView)

from spyder_modelx.widgets.mxcodeeditor import BaseCodePane


class CodePane(BaseCodePane):

    def __init__(self, parent, title='', code=''):
        super().__init__(parent, title, code)

        self.editor.setReadOnly(True)
        self.setCode(code)

    def setCode(self, code):
        self.editor.set_text(code)
        self.editor.setFixedHeight(
            self.getEditorHeight(self.editor.blockCount() + 2))

    def getEditorHeight(self, nRows):

        pdoc = self.editor.document()
        fm = self.editor.fontMetrics()
        margins = self.editor.contentsMargins()

        nHeight = fm.lineSpacing() * nRows\
                  + (pdoc.documentMargin() + self.editor.frameWidth()) * 2 \
                  + margins.top() + margins.bottom()

        return nHeight


class CodeList(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.plugin = parent.plugin

    def insertCode(self, index, title='', code=''):
        codepane = CodePane(self, title, code)

        if index < self.layout.count():
            self.layout.insertWidget(index, codepane)
        else:
            self.layout.addWidget(codepane)

    def removeCode(self, index):
        item = self.layout.takeAt(index)
        item.widget().deleteLater()

    def removeAll(self):
        for _ in range(self.layout.count()):
            self.removeCode(0)

    def appendCode(self, title='', code=''):
        codepane = CodePane(self, title, code)
        self.layout.addWidget(codepane)


class CodeListModel(QAbstractListModel):

    def __init__(self, parent=None, data=None):
        super().__init__(parent)

        if data is None:
            data = []

        self.formulas = data

    def rowCount(self, parent):
        return len(self.formulas)

    def data(self, index, role):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        return self.formulas[index.row()]


class CodeListDataWrapper:
    """Wrap attribute list to list-like"""

    def __init__(self, attrdict):

        self.items = attrdict['items']
        self.names = list(self.items.keys())

    def __getitem__(self, index):
        value = self.items[self.names[index]]
        return {'name': value['name'],
                'formula': value['formula']['source']}

    def __len__(self):
        return len(self.items)


class MxCodeListWidget(QScrollArea):

    def __init__(self, parent):
        QScrollArea.__init__(self, parent)

        self._parent = parent
        self.plugin = parent.plugin
        self.codelist = CodeList(self)
        self.model_ = None
        self.setWidget(self.codelist)
        self.setWidgetResizable(True)

    def setModel_(self, model):
        self.model_ = model
        self.updateList()

    def updateList(self):
        self.codelist.removeAll()
        for i in range(self.model_.rowCount(None)):
            index = self.model_.index(i)
            item = self.model_.data(index, Qt.DisplayRole)
            self.codelist.appendCode(item['name'],
                                     item['formula'])

    def process_remote_view(self, data):
        if data is None:
            return
        self._parent.raise_tab(self)
        data = CodeListDataWrapper(data)
        model = CodeListModel(parent=self, data=data)
        self.setModel_(model)


# ---- Test MxCodeListWidget ----

sampletexts = [
    {'name': 'SizeExpsAcq',
     'formula': dedent('''\
        def SizeExpsAcq(t):
            """Acquisition expense per policy at time t"""
            if t == 0:
                return (SizeAnnPrem(t) * asmp.ExpsAcqAnnPrem
                        + (SizeSumAssured(t) * asmp.ExpsAcqSA + asmp.ExpsAcqPol)
                        * scen.InflFactor(t) / scen.InflFactor(0))
            else:
                return 0
            print('foo')
            print('foo')
            print('foo')
            print('foo')
            print('foo')
            print('foo')        
        ''')},
    {'name': 'SizeExpsMaint',
     'formula': dedent('''\
        def SizeExpsMaint(t):
            """Maintenance expense per policy at time t"""
            return (SizeAnnPrem(t) * asmp.ExpsMaintAnnPrem
                    + (SizeSumAssured(t) * asmp.ExpsMaintSA + asmp.ExpsMaintPol)
                    * scen.InflFactor(t))
        ''')},
    {'name': 'SizeExpsOther',
     'formula': dedent('''\
        def SizeExpsOther(t):
            """Other expenses per policy at time t"""
            return 0''')}] * 3


def testsample():
    from spyder.utils.qthelpers import qapplication
    app = qapplication(test_time=5)
    win = QMainWindow(None)
    codewidget = MxCodeListWidget(win)
    win.setCentralWidget(codewidget)
    codewidget.setWidgetResizable(True)
    codewidget.setModel(CodeListModel(win, sampletexts))
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    testsample()
