# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Fumito Hamamura
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""modelx Plugin."""

from qtpy.QtWidgets import QVBoxLayout
from jupyter_core.paths import jupyter_config_dir, jupyter_runtime_dir

try:
    from spyder.api.plugins import SpyderPluginWidget
except ImportError:
    from spyder.plugins import SpyderPluginWidget # Spyder3
try:
    from spyder.api.preferences import PluginConfigPage
except ImportError:
    from spyder.plugins.configdialog import PluginConfigPage # Spyder3

from qtpy.QtCore import Qt, Signal, Slot

import spyder
from spyder.config.base import (_, DEV, get_conf_path, get_home_dir,
                                get_module_path)
from spyder.utils import icon_manager as ima
from spyder.py3compat import is_string, PY2, to_text_string
from spyder.config.main import CONF
from spyder.utils import encoding, programs, sourcecode
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton)
from spyder.plugins.ipythonconsole import IPythonConsole

from spyder_modelx.kernelspec import ModelxKernelSpec
from spyder_modelx.widgets.modelxgui import ModelxWidget, ModelxClientWidget



class ModelxConfigPage(PluginConfigPage):
    """modelx plugin preferences."""

    def setup_page(self):
        pass


class ModelxPlugin(SpyderPluginWidget):
    """modelx plugin."""
    CONF_SECTION = 'modelx'

    CONFIGWIDGET_CLASS = ModelxConfigPage


    def __init__(self, parent=None):
        SpyderPluginWidget.__init__(self, parent)
        self.main = parent # Spyder3

        # Create widget and add to dockwindow
        self.widget = ModelxWidget(self.main)
        layout = QVBoxLayout()
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # Initialize plugin
        self.initialize_plugin()

    # --- SpyderPluginWidget API ----------------------------------------------
    def get_plugin_title(self):
        """Return widget title."""
        return "modelx"

    def get_focus_widget(self):
        """Return the widget to give focus to."""
        return self.widget

    def refresh_plugin(self):
        """Refresh ModelxWidget widget."""
        pass

    def get_plugin_actions(self):
        """Return a list of actions related to plugin."""

        create_client_action = create_action(
                                   self,
                                   _("Open an &modelx console"),
                                   icon=ima.icon('ipython_console'),
                                   triggered=self.create_new_client,
                                   context=Qt.WidgetWithChildrenShortcut)

        # Add the action to the 'Consoles' menu on the main window
        main_consoles_menu = self.main.consoles_menu_actions
        main_consoles_menu.insert(0, create_client_action)
        self.main.ipyconsole.menu_actions.insert(0, create_client_action)

        # Plugin actions
        self.menu_actions = [create_client_action]  # , MENU_SEPARATOR,
                             # restart_action, connect_to_kernel_action,
                             # MENU_SEPARATOR, rename_tab_action]

        add_actions(self.main.ipyconsole.tabwidget.menu,
                    self.menu_actions,
                    insert_before=main_consoles_menu[1])

        return self.menu_actions


    def register_plugin(self):
        """Register plugin in Spyder's main window."""
        self.main.add_dockwidget(self)

    def on_first_registration(self):
        """Action to be performed on first plugin registration."""
        self.main.tabify_plugins(self.main.help, self)

    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings."""
        pass


    @Slot()
    @Slot(bool)
    @Slot(str)
    @Slot(bool, str)
    @Slot(bool, bool)
    @Slot(bool, str, bool)
    def create_new_client(self, give_focus=True, filename='', is_cython=False):
        """Create a new client

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipyconsole = self.main.ipyconsole

        ipyconsole.master_clients += 1
        client_id = dict(int_id=to_text_string(ipyconsole.master_clients),
                         str_id='A')
        cf = ipyconsole._new_connection_file()
        show_elapsed_time = ipyconsole.get_option('show_elapsed_time')
        reset_warning = ipyconsole.get_option('show_reset_namespace_warning')
        client = ModelxClientWidget(self,
            id_=client_id,
            history_filename=get_conf_path('history.py'),
            config_options=ipyconsole.config_options(),
            additional_options=ipyconsole.additional_options(),
            interpreter_versions=ipyconsole.interpreter_versions(),
            connection_file=cf,
            menu_actions=self.menu_actions,
            show_elapsed_time=show_elapsed_time,
            reset_warning=reset_warning)

        if ipyconsole.testing:
            client.stderr_dir = ipyconsole.test_dir
        ipyconsole.add_tab(client, name=client.get_name(), filename=filename)

        if cf is None:
            error_msg = ipyconsole.permission_error_msg.format(jupyter_runtime_dir())
            client.show_kernel_error(error_msg)
            return

        # Check if ipykernel is present in the external interpreter.
        # Else we won't be able to create a client
        if not CONF.get('main_interpreter', 'default'):
            pyexec = CONF.get('main_interpreter', 'executable')
            has_ipykernel = programs.is_module_installed('ipykernel',
                                                         interpreter=pyexec)
            has_cloudpickle = programs.is_module_installed('cloudpickle',
                                                           interpreter=pyexec)
            if not (has_ipykernel and has_cloudpickle):
                client.show_kernel_error(_("Your Python environment or "
                                     "installation doesn't "
                                     "have the <tt>ipykernel</tt> and "
                                     "<tt>cloudpickle</tt> modules "
                                     "installed on it. Without these modules "
                                     "is not possible for Spyder to create a "
                                     "console for you.<br><br>"
                                     "You can install them by running "
                                     "in a system terminal:<br><br>"
                                     "<tt>pip install ipykernel cloudpickle</tt>"
                                     "<br><br>"
                                     "or<br><br>"
                                     "<tt>conda install ipykernel cloudpickle</tt>"))
                return

        self.connect_client_to_kernel(client, is_cython=is_cython)
        if client.shellwidget.kernel_manager is None:
            return
        ipyconsole.register_client(client)


    def connect_client_to_kernel(self, client, is_cython=False):
        """Connect a client to its kernel

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipyconsole = self.main.ipyconsole

        connection_file = client.connection_file

        if ipyconsole.test_no_stderr:
            stderr_file = None
        else:
            stderr_file = client.stderr_file

        km, kc = self.create_kernel_manager_and_kernel_client(
                     connection_file,
                     stderr_file,
                     is_cython=is_cython)

        # An error occurred if this is True
        if is_string(km) and kc is None:
            client.shellwidget.kernel_manager = None
            client.show_kernel_error(km)
            return

        kc.started_channels.connect(lambda c=client: ipyconsole.process_started(c))
        kc.stopped_channels.connect(lambda c=client: ipyconsole.process_finished(c))
        kc.start_channels(shell=True, iopub=True)

        shellwidget = client.shellwidget
        shellwidget.kernel_manager = km
        shellwidget.kernel_client = kc


    def create_kernel_spec(self, is_cython=False):
        """Create a kernel spec for our own kernels

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipyconsole = self.main.ipyconsole
        # Before creating our kernel spec, we always need to
        # set this value in spyder.ini
        if not ipyconsole.testing:
            CONF.set('main', 'spyder_pythonpath',
                     ipyconsole.main.get_spyder_pythonpath())
        return ModelxKernelSpec(is_cython=is_cython)


    def create_kernel_manager_and_kernel_client(self, connection_file,
                                                stderr_file, is_cython=False):

        if spyder.version_info < (3, 2, 8):
            return IPythonConsole.create_kernel_manager_and_kernel_client(
                self, connection_file, stderr_file)
        else:
            return IPythonConsole.create_kernel_manager_and_kernel_client(
                self, connection_file, stderr_file, is_cython=is_cython)