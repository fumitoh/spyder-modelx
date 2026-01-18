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

from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QVBoxLayout
import spyder

from spyder.config.base import _
from spyder.api.preferences import PluginConfigPage
from spyder.api.plugin_registration.decorators import on_plugin_available
from spyder.plugins.ipythonconsole.widgets.main_widget import (
    IPythonConsoleWidgetOptionsMenuSections)

if spyder.version_info > (5, 4, 0):
    from spyder.plugins.ipythonconsole.widgets.main_widget import (
        IPythonConsoleWidgetTabsContextMenuSections
    )

from spyder_modelx.widgets.mxexplorer import MxMainWidget
from .stacked_mixin import MxStackedMixin

# New plugin API since Spyder 5
from spyder.plugins.mainmenu.api import (
    ApplicationMenus, ConsolesMenuSections)
from spyder.api.plugins import SpyderDockablePlugin, Plugins
from qtpy.QtGui import QIcon
from spyder.api.widgets.main_widget import PluginMainWidget


class MxPluginMainWidgetActions:

    OpenNewConsole = 'new_console'
    ConnectToKernel = 'connect_to_kernel'
    SelectInDataView = 'select_in_dataview'
    SelectInNewDataView = 'select_in_new_dataview'
    AnalyzePreds = 'analyze_preds'
    AnalyzeDeps = 'analyze_deps'


class MxPluginMainWidgetMainToolBarSections:
    Main = 'main_section'


class MxPluginMainWidgetOptionsMenuSections:
    Consoles = 'mx_consoles_section'


class MxConsoleWidgetTabsContextMenuSections:
    Consoles = 'mx_tabs_consoles_section'


class MxPluginMainWidgetBase(MxStackedMixin, PluginMainWidget):

    MX_WIDGET_CLASS = MxMainWidget

    def __init__(self, name=None, plugin=None, parent=None):
        PluginMainWidget.__init__(self, name, plugin, parent)
        MxStackedMixin.__init__(self, parent=parent)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        self.setLayout(layout)

        if spyder.version_info > (5, 2):
            self.ipyconsole = plugin.get_plugin(Plugins.IPythonConsole).get_widget()
        else:
            self.ipyconsole = plugin.get_plugin(Plugins.IPythonConsole)

        # To avoid circular dependency,
        # Set by MxAnalyzer and MxDataViewer's register method
        # calling set_child_plugin
        self.analyzer = None
        self.dataview = None

    def set_child_plugin(self, attr, widget):
        setattr(self, attr, widget)

    # --- API: methods to define or override
    # ------------------------------------------------------------------------
    def get_title(self):
        """
        Return the title that will be displayed on dockwidget or window title.
        """
        return _('MxExplorer')

    def setup(self):
        """
        Create widget actions, add to menu and other setup requirements.
        """

        # ---- Toolbar actions
        self.select_dataview_action = select_dataview_action = self.create_action(
            MxPluginMainWidgetActions.SelectInDataView,
            text=_('Select in DataView'),
            icon=self.create_icon('newwindow'),
            triggered=self.select_in_dataview
        )

        self.select_new_dataview_action = select_new_dataview = self.create_action(
            MxPluginMainWidgetActions.SelectInNewDataView,
            text=_('Select in New DataView'),
            icon=self.create_icon('newwindow'),
            triggered=self.select_in_new_dataview
        )

        self.create_client_action = new_console_action = self.create_action(
            MxPluginMainWidgetActions.OpenNewConsole,
            text=_('New MxConsole'),
            icon=self.create_icon('ipython_console'),
            triggered=self.create_new_client
        )

        self.connect_to_kernel_action = self.create_action(
               MxPluginMainWidgetActions.ConnectToKernel,
               text=_("Connect to an existing MxKernel"),
               icon=None,
               tip=_("Open a new IPython console connected to an existing MxKernel"),
               triggered=self.create_client_for_kernel
        )

        # Options menu
        options_menu = self.ipyconsole.get_options_menu()
        for item in [new_console_action, self.connect_to_kernel_action]:
            # Bypass SpyderMenuMixin.add_item_to_menu because of missing before_section parameter.
            options_menu.add_action(
                item,
                section=MxPluginMainWidgetOptionsMenuSections.Consoles,
                before_section=IPythonConsoleWidgetOptionsMenuSections.Consoles
            )

        # Main toolbar
        main_toolbar = self.get_main_toolbar()
        for item in [select_dataview_action, select_new_dataview]:
            self.add_item_to_toolbar(
                item,
                toolbar=main_toolbar,
                section=MxPluginMainWidgetMainToolBarSections.Main,
            )

        if spyder.version_info > (5, 4, 0):
            # Tabs context menu
            tabs_context_menu = self.ipyconsole.tabwidget.menu
            for item in [new_console_action, self.connect_to_kernel_action]:
                tabs_context_menu.add_action(
                    item,
                    section=MxConsoleWidgetTabsContextMenuSections.Consoles,
                    before_section=IPythonConsoleWidgetTabsContextMenuSections.Consoles,
                )

    def update_actions(self):
        """
        Update the state of exposed actions.

        Exposed actions are actions created by the self.create_action method.
        """
        pass

    def select_in_dataview(self):
        self.current_widget().explorer.treeview.select_in_dataview()

    def select_in_new_dataview(self):
        self.current_widget().explorer.treeview.select_in_new_dataview()


class ModelxConfigPage(PluginConfigPage):
    """modelx plugin preferences."""

    def get_name(self):
        return _('modelx')

    def setup_page(self):
        pass


class ModelxPlugin(SpyderDockablePlugin):
    """modelx plugin."""

    NAME = 'modelx_plugin'
    WIDGET_CLASS = None # To be defined in each version
    REQUIRES = [Plugins.IPythonConsole, Plugins.MainMenu]
    CONF_SECTION = 'modelx'
    CONFIGWIDGET_CLASS = ModelxConfigPage
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
        return _('MxExplorer')

    def get_description(self):
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
        return _('Main widget of the plugin for modelx')

    def get_icon(self):
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
        pass

    # register renamed to on_initialize from Spyder 5.1
    def on_initialize(self):
        pass

    @on_plugin_available(plugin=Plugins.IPythonConsole)
    def on_main_menu_available(self):
        widget = self.get_widget()
        mainmenu = self.get_plugin(Plugins.MainMenu)

        # Add signal to update actions state before showing the menu
        console_menu = mainmenu.get_application_menu(
            ApplicationMenus.Consoles)

        for console_new_action in [widget.create_client_action, widget.connect_to_kernel_action]:
            mainmenu.add_item_to_application_menu(
                console_new_action,
                menu_id=ApplicationMenus.Consoles,
                before_section=ConsolesMenuSections.New,
            )
