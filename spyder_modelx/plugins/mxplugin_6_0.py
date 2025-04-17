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

# from qtpy.QtWidgets import QVBoxLayout
from qtpy.QtGui import QIcon
import spyder
from spyder.api.plugins import Plugins
from spyder.api.shellconnect.mixins import ShellConnectPluginMixin
from spyder.api.plugins import SpyderDockablePlugin
from spyder.api.plugin_registration.decorators import on_plugin_available
from spyder.plugins.mainmenu.api import (
    ApplicationMenus, ConsolesMenuSections)

# from .mxplugin_6_base import ModelxPlugin as _ModelxPlugin, MxPluginMainWidgetBase
from .mxconsole_6_0 import MxConsoleAPI_6_0

# class MxPluginMainWidget_6_0(MxConsoleAPI_6_0, MxPluginMainWidgetBase):
#     pass

# class ModelxPlugin_6_0(_ModelxPlugin, ShellConnectPluginMixin):
#     WIDGET_CLASS = MxPluginMainWidget_6_0
#     # REQUIRES = [Plugins.IPythonConsole]


from .shellconnect import MxShellConnectMainWidget

from .mxplugin_5_base import (
    _,
    Plugins,
    ModelxConfigPage,
    IPythonConsoleWidgetTabsContextMenuSections,
    MxPluginMainWidgetActions,
    MxPluginMainWidgetMainToolBarSections,
    MxPluginMainWidgetOptionsMenuSections,
    MxConsoleWidgetTabsContextMenuSections
)
from spyder_modelx.widgets.mxexplorer import MxMainWidget

class MxPluginMainWidget(MxConsoleAPI_6_0, MxShellConnectMainWidget):

    MX_WIDGET_CLASS = MxMainWidget

    def __init__(self, name=None, plugin=None, parent=None):
        super().__init__(name, plugin, parent)

        # Layout
        # layout = QVBoxLayout()
        # layout.addWidget(self.stack)
        # self.setLayout(layout)

        self.ipyconsole = plugin.get_plugin(Plugins.IPythonConsole).get_widget()

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
               triggered=self._create_client_for_kernel
        )

        if spyder.version_info < (6,):
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



class ModelxPlugin(SpyderDockablePlugin, ShellConnectPluginMixin):
    """modelx plugin."""

    NAME = 'modelx_plugin'
    WIDGET_CLASS = MxPluginMainWidget
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
        return _('Main widget of the plugin for modelx')

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
        pass

    # register renamed to on_initialize from Spyder 5.1
    def on_initialize(self):
        pass

    # Do not override @on_plugin_available(plugin=Plugins.IPythonConsole)

    @on_plugin_available(plugin=Plugins.MainMenu)
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




