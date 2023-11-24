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
import os.path
import sys
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (QLabel, QVBoxLayout, QWidget, QMenu,
                            QMainWindow, QScrollArea, QSplitter,
                            QAbstractItemView)

import spyder
if spyder.version_info < (4,):
    from spyder.config.gui import get_shortcut
    from spyder.widgets.sourcecode.codeeditor import (
        create_action,
        ima,
        _,
        CodeEditor,
        CONF,
        add_actions,
        to_text_string,
        QTextCursor
    )
else:
    from spyder.plugins.editor.widgets.codeeditor import (
        create_action,
        ima,
        _,
        CodeEditor,
        CONF,
        add_actions,
        to_text_string,
        QTextCursor
    )


class MxCodeEditor(CodeEditor):

    if spyder.version_info < (4,):

        def setup_context_menu(self):
            """Setup context menu"""
            self.undo_action = create_action(
                self, _("Undo"), icon=ima.icon('undo'),
                shortcut=get_shortcut('editor', 'undo'), triggered=self.undo)
            self.redo_action = create_action(
                self, _("Redo"), icon=ima.icon('redo'),
                shortcut=get_shortcut('editor', 'redo'), triggered=self.redo)
            self.cut_action = create_action(
                self, _("Cut"), icon=ima.icon('editcut'),
                shortcut=get_shortcut('editor', 'cut'), triggered=self.cut)
            self.copy_action = create_action(
                self, _("Copy"), icon=ima.icon('editcopy'),
                shortcut=get_shortcut('editor', 'copy'), triggered=self.copy)
            self.paste_action = create_action(
                self, _("Paste"), icon=ima.icon('editpaste'),
                shortcut=get_shortcut('editor', 'paste'),
                triggered=self.paste)
            selectall_action = create_action(
                self, _("Select All"), icon=ima.icon('selectall'),
                shortcut=get_shortcut('editor', 'select all'),
                triggered=self.selectAll)
            toggle_comment_action = create_action(
                self, _("Comment")+"/"+_("Uncomment"), icon=ima.icon('comment'),
                shortcut=get_shortcut('editor', 'toggle comment'),
                triggered=self.toggle_comment)

            # Build menu
            self.menu = QMenu(self)
            actions_1 = [self.undo_action,
                         self.redo_action, None, self.cut_action,
                         self.copy_action, self.paste_action, selectall_action]
            actions_2 = [None, toggle_comment_action]
            actions = actions_1 + actions_2
            add_actions(self.menu, actions)

            # Read-only context-menu
            self.readonly_menu = QMenu(self)
            add_actions(self.readonly_menu,
                        (self.copy_action, selectall_action))

    else:

        def setup_context_menu(self):
            """Setup context menu"""
            self.undo_action = create_action(
                self, _("Undo"), icon=ima.icon('undo'),
                shortcut=CONF.get_shortcut('editor', 'undo'), triggered=self.undo)
            self.redo_action = create_action(
                self, _("Redo"), icon=ima.icon('redo'),
                shortcut=CONF.get_shortcut('editor', 'redo'), triggered=self.redo)
            self.cut_action = create_action(
                self, _("Cut"), icon=ima.icon('editcut'),
                shortcut=CONF.get_shortcut('editor', 'cut'), triggered=self.cut)
            self.copy_action = create_action(
                self, _("Copy"), icon=ima.icon('editcopy'),
                shortcut=CONF.get_shortcut('editor', 'copy'), triggered=self.copy)
            self.paste_action = create_action(
                self, _("Paste"), icon=ima.icon('editpaste'),
                shortcut=CONF.get_shortcut('editor', 'paste'),
                triggered=self.paste)
            selectall_action = create_action(
                self, _("Select All"), icon=ima.icon('selectall'),
                shortcut=CONF.get_shortcut('editor', 'select all'),
                triggered=self.selectAll)
            toggle_comment_action = create_action(
                self, _("Comment")+"/"+_("Uncomment"), icon=ima.icon('comment'),
                shortcut=CONF.get_shortcut('editor', 'toggle comment'),
                triggered=self.toggle_comment)

            # Build menu
            self.menu = QMenu(self)
            actions_1 = [self.undo_action,
                         self.redo_action, None, self.cut_action,
                         self.copy_action, self.paste_action, selectall_action]
            actions_2 = [None, toggle_comment_action]
            actions = actions_1 + actions_2
            add_actions(self.menu, actions)

            # Read-only context-menu
            self.readonly_menu = QMenu(self)
            add_actions(self.readonly_menu,
                        (self.copy_action, selectall_action))

    def contextMenuEvent(self, event):
        """Reimplement Qt method"""
        nonempty_selection = self.has_selected_text()
        self.copy_action.setEnabled(nonempty_selection)
        self.cut_action.setEnabled(nonempty_selection)

        # Code duplication go_to_definition_from_cursor and mouse_move_event
        cursor = self.textCursor()
        text = to_text_string(cursor.selectedText())
        if len(text) == 0:
            cursor.select(QTextCursor.WordUnderCursor)
            text = to_text_string(cursor.selectedText())

        self.undo_action.setEnabled(self.document().isUndoAvailable())
        self.redo_action.setEnabled(self.document().isRedoAvailable())
        menu = self.menu
        if self.isReadOnly():
            menu = self.readonly_menu
        menu.popup(event.globalPos())
        event.accept()


class BaseCodePane(QWidget):

    def __init__(self, parent, title='', code='', editor_type=MxCodeEditor):
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

        editor.setup_editor(linenumbers=True, language='Python',
                            markers=True, tab_mode=False,
                            font=font,
                            show_blanks=False,
                            color_scheme=color_scheme,
                            scrollflagarea=False)

        editor.fontMetrics().lineSpacing()

        # Unhighlight and rehighlight current line to prevent a visual glitch
        # when opening files.
        # Fixes spyder-ide/spyder#20033
        editor.unhighlight_current_line()
        editor.highlight_current_line()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        if title:
            self.layout.addWidget(QLabel(title))
        self.layout.addWidget(editor)  # , stretch=1)
        self.setLayout(self.layout)


# =============================================================================
# Editor + Class browser test
# =============================================================================
class TestWidget(QSplitter):
    def __init__(self, parent):
        QSplitter.__init__(self, parent)
        self.editor = MxCodeEditor(self)
        self.editor.setup_editor(linenumbers=True, markers=True, tab_mode=False,
                                 font=QFont("Courier New", 10),
                                 show_blanks=True, color_scheme='Spyder')
        self.addWidget(self.editor)
        self.setWindowIcon(ima.icon('spyder'))

    def load(self, filename):
        self.editor.set_text_from_file(filename)
        self.setWindowTitle("%s - %s (%s)" % (_("Editor"),
                                              os.path.basename(filename),
                                              os.path.dirname(filename)))
        self.editor.hide_tooltip()


def test(fname):
    from spyder.utils.qthelpers import qapplication
    app = qapplication(test_time=5)
    win = TestWidget(None)
    win.show()
    win.load(fname)
    win.resize(900, 700)
    sys.exit(app.exec_())


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fname = sys.argv[1]
    else:
        fname = __file__
    test(fname)
