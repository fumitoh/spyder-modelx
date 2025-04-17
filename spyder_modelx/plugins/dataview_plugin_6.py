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

# The source code contains parts copied and modified from Spyder project:
# https://github.com/spyder-ide/spyder
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

import sys
import ast

from qtpy.QtWidgets import (
    QVBoxLayout, QWidget, QLabel, QButtonGroup, QRadioButton, QGridLayout,
    QHBoxLayout, QPushButton, QMessageBox
)

import spyder

from spyder.api.plugins import Plugins
from spyder.api.shellconnect.mixins import ShellConnectPluginMixin

from spyder.widgets.tabs import Tabs
from spyder.utils.qthelpers import create_plugin_layout, create_action
from spyder.api.fonts import SpyderFontType

from spyder_modelx.widgets.mxdataviewer import (
    MxDataFrameViewer,
    MxArrayViewer,
    MxCollectionsViewer
)

from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin
from spyder_modelx.widgets.mxlineedit import MxPyExprLineEdit
from spyder.config.base import _
from .shellconnect import MxShellConnectMainWidget
from .stacked_mixin import MxStackedMixin



class MxDataViewTabs(Tabs):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, menu=parent._options_menu)
        self.plugin = parent.get_plugin()
        self.set_close_function(self.close_tab)
        self.add_tab()

    def add_tab(self):
        index = self.addTab(MxDataViewWidget(self), '<Empty>')
        self.setCurrentIndex(index)

    def set_shellwidget(self, shellwidget):
        self.shellwidget = shellwidget
        self.shellwidget.set_mxdataview(self)

    def update_object(self, data):
        self.currentWidget().update_object(data)

    def update_data(self):
        self.currentWidget().update_data()

    def update_value(self, data):
        self.currentWidget().update_value(data)

    def clear_contents(self):
        self.currentWidget().clear_contents()

    def close_tab(self, index=None, tab=None, force=False):
        """Close client tab from index or widget (or close current tab)"""
        if not self.count():
            return
        elif self.count() == 1:
            QMessageBox.critical(self, "Error", "Cannot close last tab.")
            return

        if tab is not None:
            if tab not in [self.widget(i) for i in range(self.count())]:
                # Client already closed
                return
            index = self.tabwidget.indexOf(tab)
            # if index is not found in tabwidget it's because this client was
            # already closed and the call was performed by the exit callback
            if index == -1:
                return
        if index is None and tab is None:
            index = self.currentIndex()
        if index is not None:
            tab = self.widget(index)

        # Note: client index may have changed after closing related widgets
        self.removeTab(self.indexOf(tab))


class MxDataViewWidget(QWidget):

    def __init__(self, parent, **kwargs):
        QWidget.__init__(self, parent)

        self.plugin = parent.plugin
        self.parent = parent

        # ---- Layouts an widgets in MxDataViewWidget ---
        #
        # main_layout
        #   outer_layout
        #       upper_layout
        #           objbox_layout         update_button
        #               objbox  argbox
        #
        #       self.msgbox
        #   self.widget
        #

        update_button = QPushButton(text="Update", parent=self)
        update_button.clicked.connect(self.update_data)

        font = self.plugin.get_font(font_type=SpyderFontType.Interface)
        self.objbox = QLabel(parent=self)
        self.argbox = MxPyExprLineEdit(self, font=font)
        self.msgbox = QLabel(parent=self)
        self.msgbox.setText("")
        self.msgbox.setWordWrap(True)

        outer_layout = QVBoxLayout()
        upper_layout = QHBoxLayout()
        outer_layout.addLayout(upper_layout)
        outer_layout.addWidget(self.msgbox)

        objbox_layout = QHBoxLayout()
        objbox_layout.addWidget(self.objbox)
        objbox_layout.addWidget(self.argbox)
        objbox_layout.setStretch(0, 3)  # 3:1
        objbox_layout.setStretch(1, 1)

        upper_layout.addLayout(objbox_layout)
        upper_layout.addWidget(update_button)

        # Create main widget
        self.widget = QWidget(parent=self)

        self.main_layout = main_layout = QVBoxLayout()
        main_layout.addLayout(outer_layout)
        main_layout.addWidget(self.widget)
        main_layout.setStretch(1, 1)

        margins = (0, 0, 0, 0)

        for lo in [outer_layout, upper_layout, self.msgbox]:
            lo.setContentsMargins(*margins)

        objbox_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(main_layout)

        self.attrdict = None

    @property
    def shellwidget(self):
        return self.parent.shellwidget

    def update_object(self, data):
        if data is None:
            return

        self.attrdict = data
        if data["type"] == 'Reference' or (
                data["type"] == "Cells" and not data["parameters"]):
            self.argbox.setText("")
            self.argbox.setEnabled(False)
        else:
            self.argbox.setEnabled(True)

        self.objbox.setText(data['_evalrepr'])
        self.parent.setTabText(
            self.parent.indexOf(self),
            data['name']
        )

    def update_data(self):

        argtxt = self.argbox.get_expr()
        args = "(" + argtxt + ("," if argtxt else "") + ")"
        # assert
        ast.literal_eval(args)

        calc = self.plugin.get_container().calc_on_update_action.isChecked()

        val, is_calculated = self.shellwidget.update_mxdataview(
            obj=self.attrdict["fullname"],
            args=args,
            calc=calc
        )
        self.update_value(val)
        if is_calculated:
            self.shellwidget.update_mx_widgets({})

    def update_value(self, data):

        import pandas as pd
        import numpy as np
        import numpy.ma

        if isinstance(data, (pd.DataFrame, pd.Index, pd.Series)):
            self.widget.deleteLater()
            self.widget = MxDataFrameViewer(self)
            self.widget.setup_and_check(data)
            self.msgbox.setText(data.__class__.__name__)
        elif isinstance(data, (np.ndarray, np.ma.MaskedArray)):
            self.widget.deleteLater()
            self.widget = MxArrayViewer(self)
            self.widget.setup_and_check(data, title='', readonly=True)
            self.msgbox.setText(data.__class__.__name__)
        elif isinstance(data, (list, set, tuple, dict)):
            self.widget.deleteLater()
            self.widget = MxCollectionsViewer(self)
            self.widget.setup(data, title='', readonly=True)
            self.msgbox.setText(data.__class__.__name__)
        else:
            txt = data.__class__.__name__ + ": " + repr(data)
            self.widget.deleteLater()
            self.widget = QWidget(parent=self)
            self.msgbox.setText(txt)

        self.main_layout.addWidget(self.widget)
        self.main_layout.setStretchFactor(self.widget, 1)

    def clear_contents(self):
        if self.widget:
            self.widget.deleteLater()
            self.widget = QWidget(parent=self)
            self.attrdict = None
            self.objbox.setText("")
            self.argbox.setText("")
            self.msgbox.setText("")
            self.parent.setTabText(
                self.parent.indexOf(self),
                "<Empty>"
            )
            self.main_layout.addWidget(self.widget)
            self.main_layout.setStretchFactor(self.widget, 1)




# New plugin API since Spyder 5
from spyder.api.plugins import SpyderDockablePlugin, Plugins
from qtpy.QtGui import QIcon
from spyder.api.widgets.main_widget import PluginMainWidget
# from spyder_modelx.plugins.mxplugin import ModelxConfigPage

class MxDataViewMainWidgetActions:

    AddNewTab = 'add_new_tab'
    ClearContents = 'clear_contents'
    CalcOnUpdate = 'calc_on_update'

class MxDataViewMainWidgetActionsOptionsMenuSections:

    Main = 'main_section'

class MxDataViewMainWidget(MxShellConnectMainWidget):

    MX_WIDGET_CLASS = MxDataViewTabs

    def __init__(self, name=None, plugin=None, parent=None):
        super().__init__(name, plugin, parent)
        # MxStackedMixin.__init__(self, parent=parent)

        # Layout
        # layout = QVBoxLayout()
        # layout.addWidget(self.stack)
        # self.setLayout(layout)

        self.ipyconsole = plugin.get_plugin(Plugins.IPythonConsole)

    # --- API: methods to define or override
    # ------------------------------------------------------------------------
    def get_title(self):
        """
        Return the title that will be displayed on dockwidget or window title.
        """
        return _('MxDataViewer')

    def setup(self):
        """
        Create widget actions, add to menu and other setup requirements.
        """

        # ---- Toolbar actions
        self.new_action = self.create_action(
            MxDataViewMainWidgetActions.AddNewTab,
            text=_("New tab"),
            icon=self.create_icon("newwindow"),
            triggered=self.add_new_tab
        )
        self.clear_action = self.create_action(
            MxDataViewMainWidgetActions.ClearContents,
            text=_("Clear"),
            icon=self.create_icon("editdelete"),
            triggered=self.clear_contents
        )
        self.calc_on_update_action = self.create_action(
            MxDataViewMainWidgetActions.CalcOnUpdate,
            text=_('Calculate on update'),
            tip=_('Calculate the selected if not yet calculated'),
            toggled=True
        )
        self.calc_on_update_action.setChecked(True)

        # Options menu
        options_menu = self.get_options_menu()
        for item in [self.new_action,
                     self.clear_action,
                     self.calc_on_update_action]:
            self.add_item_to_menu(
                item,
                menu=options_menu,
                section=MxDataViewMainWidgetActionsOptionsMenuSections.Main
            )

        # Widgets for the tab corner
        self.new_button = self.create_toolbutton(
            MxDataViewMainWidgetActions.AddNewTab,
            text=_("New tab"),
            tip=_("Create a new tab"),
            icon=self.create_icon("newwindow"),
            triggered=self.add_new_tab,
        )
        self.clear_button = self.create_toolbutton(
            MxDataViewMainWidgetActions.ClearContents,
            text=_("Clear"),
            tip=_("Clear"),
            icon=self.create_icon("editdelete"),
            triggered=self.clear_contents,
        )
        if spyder.version_info > (6,):
            self.add_corner_widget(self.new_button)
            self.add_corner_widget(self.clear_button)
        else:
            self.add_corner_widget(MxDataViewMainWidgetActions.AddNewTab, self.new_button)
            self.add_corner_widget(MxDataViewMainWidgetActions.ClearContents, self.clear_button)

    def add_new_tab(self):
        self.current_widget().add_tab()

    def clear_contents(self):
        self.current_widget().clear_contents()

    def update_actions(self):
        """
        Update the state of exposed actions.

        Exposed actions are actions created by the self.create_action method.
        """
        pass

class MxDataViewPlugin(SpyderDockablePlugin, ShellConnectPluginMixin):
    """modelx sub-plugin.

    This plugin in registered by the modelx main plugin.
    """
    NAME = 'mxdataviewer'
    WIDGET_CLASS = MxDataViewMainWidget
    REQUIRES = [Plugins.IPythonConsole, 'modelx_plugin']
    CONF_SECTION = 'modelx'
    CONF_FILE = False

    # -------------------------------------------------------------------
    # --- API: Mandatory methods to define ------------------------------



    @staticmethod
    def get_name():
        """
        Return the plugin localized name.

        Returns
        -------
        str
            Localized name of the plugin.

        Notes
        -----
        This is a method to be able to update localization without a restart.
        """
        return _('MxDataViewer')

    @staticmethod
    def get_description():
        """
        Return the plugin localized description.

        Returns
        -------
        str
            Localized description of the plugin.

        Notes
        -----
        This is a method to be able to update localization without a restart.
        """
        return _('Widget for tracing modelx node dependency')

    @classmethod
    def get_icon(cls):
        """
        Return the plugin associated icon.

        Returns
        -------
        QIcon
            QIcon instance
        """
        return QIcon()

    def register(self):
        """
        Setup and register plugin in Spyder's main window and connect it to
        other plugins.
        """
        self.get_plugin('modelx_plugin').get_container().set_child_plugin('dataview', self.get_container())
    # -------------------------------------------------------------------

    # register renamed to on_initialize from Spyder 5.1
    def on_initialize(self):
        """
        Setup and register plugin in Spyder's main window and connect it to
        other plugins.
        """
        self.get_plugin('modelx_plugin').get_container().set_child_plugin('dataview', self.get_container())
    # -------------------------------------------------------------------

