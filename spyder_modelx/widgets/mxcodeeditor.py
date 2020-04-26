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


from qtpy.QtGui import QFont
from qtpy.QtWidgets import (QLabel, QVBoxLayout, QWidget,
                            QMainWindow, QScrollArea,
                            QAbstractItemView)

import spyder
if spyder.version_info < (4,):
    from spyder.widgets.sourcecode.codeeditor import CodeEditor
else:
    from spyder.plugins.editor.widgets.codeeditor import CodeEditor


class BaseCodePane(QWidget):

    def __init__(self, parent, title='', code='', editor_type=CodeEditor):
        QWidget.__init__(self, parent)

        self.editor = editor = editor_type(self)
        self.plugin = plugin = parent.plugin

        if self.plugin:
            if spyder.version_info < (4,):
                font = self.plugin.get_plugin_font()
            else:
                font = self.plugin.get_font()

            color_scheme = self.plugin.get_color_scheme()
        else:
            font = QFont("Courier New", 10)
            color_scheme = 'Spyder'

        editor.setup_editor(linenumbers=False, language='Python',
                            markers=True, tab_mode=False,
                            font=font,
                            show_blanks=False,
                            color_scheme=color_scheme,
                            scrollflagarea=False)

        editor.fontMetrics().lineSpacing()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        layout.addWidget(editor)  # , stretch=1)
        self.setLayout(layout)
