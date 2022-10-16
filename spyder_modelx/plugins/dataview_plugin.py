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
try:
    from spyder.api.plugins import SpyderPluginWidget
except ImportError:
    from spyder.plugins import SpyderPluginWidget  # Spyder3

from spyder.widgets.tabs import Tabs
from spyder.utils.qthelpers import create_plugin_layout, create_action

if spyder.version_info > (5, 1):
    from spyder_modelx.widgets.mxdataviewer.dataframeviewer import MxDataFrameViewer
    from spyder_modelx.widgets.mxdataviewer.arrayviewer import MxArrayViewer
    from spyder_modelx.widgets.mxdataviewer.collectionsviewer import MxCollectionsViewer
elif spyder.version_info > (5,):
    from spyder_modelx.widgets.mxdataviewer.compat50.dataframeviewer import MxDataFrameViewer
    from spyder_modelx.widgets.mxdataviewer.compat50.arrayviewer import MxArrayViewer
    from spyder_modelx.widgets.mxdataviewer.compat50.collectionsviewer import MxCollectionsViewer
elif spyder.version_info > (4,):
    from spyder_modelx.widgets.mxdataviewer.compat401.dataframeviewer import MxDataFrameViewer
    from spyder_modelx.widgets.mxdataviewer.compat401.arrayviewer import MxArrayViewer
    from spyder_modelx.widgets.mxdataviewer.compat401.collectionsviewer import MxCollectionsViewer
else:
    from spyder_modelx.widgets.mxdataviewer.compat32.dataframeviewer import MxDataFrameViewer
    from spyder_modelx.widgets.mxdataviewer.compat32.arrayviewer import MxArrayViewer
    if spyder.version_info > (3, 3):
        from spyder_modelx.widgets.mxdataviewer.compat33.collectionsviewer import MxCollectionsViewer
    else:
        from spyder_modelx.widgets.mxdataviewer.compat32.collectionsviewer import MxCollectionsViewer

from spyder_modelx.widgets.mxtoolbar import MxToolBarMixin
from spyder_modelx.widgets.mxlineedit import MxPyExprLineEdit
from spyder.config.base import _
from .stacked_mixin import MxStackedMixin


if spyder.version_info > (5,):

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

            font = self.plugin.get_font()
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
                is_obj=True,
                obj=self.attrdict["fullname"],
                args=args,
                calc=calc
            )
            self.update_value(val)
            if is_calculated:
                self.shellwidget.refresh_namespacebrowser()

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


else:

    class MxDataViewWidget(MxToolBarMixin, QWidget):

        def __init__(self, parent, **kwargs):
            QWidget.__init__(self, parent)

            if spyder.version_info > (5,):
                self.plugin = parent.get_plugin()
            else:
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

            #
            #         outer_layout
            #        +----------------------------------------------|-----------+
            #        |   inner_layout                               |           |
            #        |  +---------|-----------------------------+   |           |
            #  upper |  |         | +----------------------+    |   |           |
            # layout |  |obj_radio| |objbox_layout         |    |   |           |
            #        |  |         | +----------------------+    |   |  update   |
            #        |  -----------------------------------------   |  button   |
            #        |  |   expr  |                             |   |           |
            #        |  |   radio |  exprbox                    |   |           |
            #        |  +---------|-----------------------------+   |           |
            #        |                                              |           |
            #        -----------------------------------------------|------------
            #        |                                                          |
            #        |   msgbox                                                 |
            #        |                                                          |
            #        +----------------------------------------------------------+
            #

            button_group = QButtonGroup(parent=self)
            self.object_radio = object_radio = QRadioButton("Object")
            self.expr_radio = expr_radio = QRadioButton("Expression")
            button_group.addButton(object_radio)
            button_group.addButton(expr_radio)

            object_radio.toggled.connect(self.activateObject)
            expr_radio.toggled.connect(self.activateExpression)

            update_button = QPushButton(text="Update", parent=self)
            update_button.clicked.connect(self.update_data)

            # txt = _("Expression")
            # if sys.platform == 'darwin':
            #     expr_label = QLabel("  " + txt)
            # else:
            #     expr_label = QLabel(txt)

            if spyder.version_info < (4,):
                font = self.plugin.get_plugin_font()
            else:
                font = self.plugin.get_font()

            self.exprbox = MxPyExprLineEdit(self, font=font)
            self.objbox = QLabel(parent=self)
            self.argbox = MxPyExprLineEdit(self, font=font)
            self.msgbox = QLabel(parent=self)
            self.msgbox.setText("")
            self.msgbox.setWordWrap(True)

            outer_layout = QVBoxLayout()
            upper_layout = QHBoxLayout()
            outer_layout.addLayout(upper_layout)
            outer_layout.addWidget(self.msgbox)

            inner_layout = QGridLayout()
            inner_layout.addWidget(object_radio, 0, 0)
            inner_layout.addWidget(expr_radio, 1, 0)
            inner_layout.addWidget(self.exprbox, 1, 1)
            objbox_layout = QHBoxLayout()
            objbox_layout.addWidget(self.objbox)
            objbox_layout.addWidget(self.argbox)
            objbox_layout.setStretch(0, 3)  # 3:1
            objbox_layout.setStretch(1, 1)
            inner_layout.addLayout(objbox_layout, 0, 1)

            upper_layout.addLayout(inner_layout)
            upper_layout.addWidget(update_button)

            # widget = QWidget(parent=self)
            # widget.setLayout(outer_layout)

            # Create main widget
            self.widget = QWidget(parent=self) # MxDataFrameViewer(self)

            self.main_layout = main_layout = QVBoxLayout()
            main_layout.addLayout(outer_layout)
            main_layout.addWidget(self.widget)
            main_layout.setStretch(1, 1)

            # Main layout of this widget
            layout = create_plugin_layout(self.tools_layout)
            layout.addLayout(main_layout)

            margins = (5, 5, 5, 5)

            for lo in [outer_layout, upper_layout, inner_layout, self.msgbox]:
                lo.setContentsMargins(*margins)

            objbox_layout.setContentsMargins(5, 5, 0, 5)

            self.setLayout(layout)

            self.attrdict = None
            object_radio.setChecked(True)

        def setup_option_actions(self, *args, **kwargs):

            self.calc_on_update = create_action(self,
               _("Calculate upon update"),
               tip=_("Calculate the selected cells if not yet calculated"),
               toggled=lambda state:
               self.sig_option_changed.emit('calc_on_update', state))
            self.calc_on_update.setChecked(True)
            self.actions = [self.calc_on_update]

        def set_shellwidget(self, shellwidget):
            """Bind shellwidget instance to namespace browser"""
            self.shellwidget = shellwidget
            self.shellwidget.set_mxdataview(self)

        # MxToolBarMixin interface method
        def setup_toolbar(self):
            return []

        def activateObject(self, checked):
            self.argbox.setEnabled(checked)
            self.exprbox.setEnabled(not checked)

        def activateExpression(self, checked):
            self.argbox.setEnabled(not checked)
            self.exprbox.setEnabled(checked)

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

        def update_data(self):
            if self.object_radio.isChecked():

                argtxt = self.argbox.get_expr()
                args = "(" + argtxt + ("," if argtxt else "") + ")"
                # assert
                ast.literal_eval(args)

                calc = self.calc_on_update.isChecked()

                val, is_calculated = self.shellwidget.update_mxdataview(
                    is_obj=True,
                    obj=self.attrdict["fullname"],
                    args=args,
                    calc=calc
                )
                self.update_value(val)
                if is_calculated:
                    self.shellwidget.refresh_namespacebrowser()

            elif self.expr_radio.isChecked():
                self.shellwidget.update_mxdataview(
                    is_obj=False,
                    expr=self.exprbox.get_expr()
                )
                self.shellwidget.refresh_namespacebrowser()
            else:
                raise RuntimeError("MxDataViewer: must not happen")

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


if spyder.version_info > (5,):

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

    class MxDataViewMainWidget(MxStackedMixin, PluginMainWidget):

        MX_WIDGET_CLASS = MxDataViewTabs

        def __init__(self, name=None, plugin=None, parent=None):
            PluginMainWidget.__init__(self, name, plugin, parent)
            MxStackedMixin.__init__(self, parent=parent)

            # Layout
            layout = QVBoxLayout()
            layout.addWidget(self.stack)
            self.setLayout(layout)

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

    class MxDataViewPlugin(SpyderDockablePlugin):
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

        # For breaking change. see https://github.com/spyder-ide/spyder/issues/16966
        if spyder.version_info > (5, 2):

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

        else:
            def get_name(self):
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
            return _('Widget for tracing modelx node dependency')

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


else:
    class MxDataViewPlugin(MxStackedMixin, SpyderPluginWidget):
        """modelx sub-plugin.

        This plugin in registered by the modelx main plugin.
        """

        CONF_SECTION = 'modelx_dataviewer'
        MX_WIDGET_CLASS = MxDataViewWidget
        CONF_FILE = False

        def __init__(self, parent=None, **kwargs):

            SpyderPluginWidget.__init__(self, parent)
            MxStackedMixin.__init__(self, parent)

            # Layout
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.stack)
            if spyder.version_info > (4,):
                self.options_button.setVisible(False)
            self.setLayout(layout)

            if spyder.version_info < (4,):
                # Initialize plugin
                self.initialize_plugin()

        # --- SpyderPluginWidget API ----------------------------------------------
        def get_plugin_title(self):
            """Return widget title."""
            return 'MxDataViewer'

        def get_focus_widget(self):
            """Return the widget to give focus to."""
            return self.current_widget()

        def refresh_plugin(self):
            """Refresh MxExplorer widget."""
            pass

        def get_plugin_actions(self):
            """Return a list of actions related to plugin"""
            widget = self.current_widget()
            if isinstance(widget, self.MX_WIDGET_CLASS):
                return widget.actions
            else:
                # Start-up Label
                return []

        def register_plugin(self):
            """Register plugin in Spyder's main window."""
            if spyder.version_info < (4,):
                self.main.add_dockwidget(self)
            else:
                self.add_dockwidget()

        def on_first_registration(self):
            """Action to be performed on first plugin registration."""
            self.main.tabify_plugins(self.main.help, self)

        def apply_plugin_settings(self, options):
            """Apply configuration file's plugin settings."""
            pass
