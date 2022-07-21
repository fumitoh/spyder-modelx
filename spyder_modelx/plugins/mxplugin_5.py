import os.path as osp

from spyder.config.base import _
from spyder.api.preferences import PluginConfigPage

from jupyter_client.connect import find_connection_file
from jupyter_core.paths import jupyter_config_dir, jupyter_runtime_dir
from qtconsole.client import QtKernelClient

from spyder.api.plugins import SpyderPluginWidget

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel,
                            QSplitter, QStackedWidget, QMessageBox)
import spyder

from spyder.config.base import DEV, get_conf_path, get_home_dir, get_module_path
from spyder.utils import icon_manager as ima
from spyder.py3compat import is_string, PY2, to_text_string

from spyder.config.manager import CONF
from spyder.utils import encoding, programs, sourcecode
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, create_plugin_layout)
from spyder.plugins.ipythonconsole.plugin import IPythonConsole
from spyder.plugins.ipythonconsole.widgets import KernelConnectionDialog

from spyder_modelx.mxkernelspec import MxKernelSpec
from spyder_modelx.widgets.mxexplorer import MxMainWidget
from spyder_modelx.widgets.mxclient import MxClientWidget

from .stacked_mixin import MxStackedMixin

# New plugin API since Spyder 5
from spyder.plugins.mainmenu.api import (
    ApplicationMenus, ConsolesMenuSections, HelpMenuSections)
from spyder.api.plugins import SpyderDockablePlugin, Plugins
from qtpy.QtGui import QIcon
from spyder.api.widgets.main_widget import PluginMainWidget

class MxPluginMainWidgetActions:

    OpenNewConsole = 'new_console'
    ConnectToKernel = 'connect_to_kernel'
    SelectInDataView = 'select_in_dataview'
    SelectInNewDataView = 'select_in_new_dataview'


class MxPluginMainWidgetMainToolBarSections:
    Main = 'main_section'


class MxPluginMainWidgetOptionsMenuSections:
    Consoles = 'mxconsoles_section'


class MxPluginMainWidget(MxStackedMixin, PluginMainWidget):

    MX_WIDGET_CLASS = MxMainWidget

    def __init__(self, name=None, plugin=None, parent=None):
        PluginMainWidget.__init__(self, name, plugin, parent)
        MxStackedMixin.__init__(self, parent=parent)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        self.setLayout(layout)

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

        create_client_action = new_console_action = self.create_action(
            MxPluginMainWidgetActions.OpenNewConsole,
            text=_('New MxConsole'),
            icon=self.create_icon('ipython_console'),
            triggered=self.create_new_client
        )

        connect_to_kernel_action = self.create_action(
               MxPluginMainWidgetActions.ConnectToKernel,
               text=_("Connect to an existing MxKernel"),
               icon=None,
               tip=_("Open a new IPython console connected to an existing MxKernel"),
               triggered=self.create_client_for_kernel
        )

        # Options menu
        options_menu = self.get_options_menu()
        for item in [new_console_action, connect_to_kernel_action]:
            self.add_item_to_menu(
                item,
                menu=options_menu,
                section=MxPluginMainWidgetOptionsMenuSections.Consoles
            )

        # Main toolbar
        main_toolbar = self.get_main_toolbar()
        for item in [select_dataview_action, select_new_dataview]:
            self.add_item_to_toolbar(
                item,
                toolbar=main_toolbar,
                section=MxPluginMainWidgetMainToolBarSections.Main,
            )

        if spyder.version_info > (5, 0, 3):

            mx_actions = [create_client_action, connect_to_kernel_action]

            for console_new_action in mx_actions:
                self.main.mainmenu.add_item_to_application_menu(
                    console_new_action,
                    menu_id=ApplicationMenus.Consoles,
                    section=ConsolesMenuSections.New)

            # Plugin actions : MxConsole
            self.menu_actions = mx_actions + self.ipyconsole.menu_actions.copy()

            # TODO: Default IPython Console
            for i, act in enumerate(mx_actions):
                self.ipyconsole.menu_actions.insert(i, act)

        else:
            # Add the action to the 'Consoles' menu on the main window
            main_consoles_menu = self.main.consoles_menu_actions
            main_consoles_menu.insert(0, create_client_action)
            main_consoles_menu.insert(1, connect_to_kernel_action)
            self.main.ipyconsole.menu_actions.insert(0, create_client_action)
            self.main.ipyconsole.menu_actions.insert(1, connect_to_kernel_action)

            # Plugin actions
            self.menu_actions = [connect_to_kernel_action, create_client_action] + \
                                self.main.ipyconsole.menu_actions.copy()

            add_actions(self.main.ipyconsole.tabwidget.menu,
                        [connect_to_kernel_action, create_client_action],
                        insert_before=main_consoles_menu[1])

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

    # --- IPython Console methods
    # ------------------------------------------------------------------------
    @Slot()
    @Slot(bool)
    @Slot(str)
    @Slot(bool, str)
    @Slot(bool, bool)
    @Slot(bool, str, bool)
    def create_new_client(self, give_focus=True, filename='', is_cython=False,
                          **kwargs):
        """Create a new client

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.ipyconsole

        ipycon.master_clients += 1
        client_id = dict(int_id=to_text_string(ipycon.master_clients),
                         str_id='A')
        cf = ipycon._new_connection_file()
        show_elapsed_time = ipycon.get_option('show_elapsed_time')
        reset_warning = ipycon.get_option('show_reset_namespace_warning')
        client_kwargs = {
            "ask_before_restart": ipycon.get_option('ask_before_restart'),
            "ask_before_closing": ipycon.get_option('ask_before_closing'),
            "options_button": ipycon.options_button,
            "css_path": ipycon.css_path
        }
        if "given_name" in kwargs:  # if not use default 'MxConsole'
            client_kwargs["given_name"] = kwargs["given_name"]


        addops = {}
        if "is_pylab" in kwargs:
            addops["is_pylab"] = kwargs["is_pylab"]
        if "is_sympy" in kwargs:
            addops["is_sympy"] = kwargs["is_sympy"]

        client = MxClientWidget(ipycon,
                                id_=client_id,
                                history_filename=get_conf_path('history.py'),
                                config_options=ipycon.config_options(),
                                additional_options=ipycon.additional_options(**addops),
                                interpreter_versions=ipycon.interpreter_versions(),
                                connection_file=cf,
                                menu_actions=self.menu_actions,
                                show_elapsed_time=show_elapsed_time,
                                reset_warning=reset_warning,
                                **client_kwargs)

        # Change stderr_dir if requested
        testing = (ipycon.test_dir is not None)
        if testing:
            client.stderr_dir = ipycon.test_dir

        ipycon.add_tab(client, name=client.get_name(), filename=filename)

        if cf is None:
            error_msg = ipycon.permission_error_msg.format(jupyter_runtime_dir())
            client.show_kernel_error(error_msg)
            return

        # Check if ipykernel is present in the external interpreter.
        # Else we won't be able to create a client
        if not CONF.get('main_interpreter', 'default'):
            pyexec = CONF.get('main_interpreter', 'executable')
            has_ipykernel = programs.is_module_installed(
                "spyder_kernels",
                interpreter=pyexec)     # missing version param
            testcond = has_ipykernel

            if not testcond:
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
        ipycon.register_client(client)

    @Slot()
    def create_client_for_kernel(self):
        """Create a client connected to an existing kernel"""
        connect_output = KernelConnectionDialog.get_connection_parameters(self)
        (connection_file, hostname, sshkey, password, ok) = connect_output
        if not ok:
            return
        else:
            self._create_client_for_kernel(connection_file, hostname, sshkey,
                                           password)

    def connect_client_to_kernel(self, client, is_cython=False,
                                 **kwargs):    # kwargs for is_pylab, is_sympy
        """Connect a client to its kernel

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.main.ipyconsole

        connection_file = client.connection_file

        if ipycon.test_no_stderr:
            stderr_handle = None
        else:
            stderr_handle = client.stderr_handle

        km, kc = self.create_kernel_manager_and_kernel_client(
            connection_file,
            stderr_handle,
            is_cython=is_cython, **kwargs)

        # An error occurred if this is True
        if is_string(km) and kc is None:
            client.shellwidget.kernel_manager = None
            client.show_kernel_error(km)
            return

        # This avoids a recurrent, spurious NameError when running our
        # tests in our CIs
        if not ipycon.testing:
            kc.started_channels.connect(
                lambda c=client: self.process_started(c))
            kc.stopped_channels.connect(
                lambda c=client: self.process_finished(c))
        kc.start_channels(shell=True, iopub=True)

        shellwidget = client.shellwidget
        shellwidget.set_kernel_client_and_manager(kc, km)
        shellwidget.sig_exception_occurred.connect(
            self.main.console.handle_exception)

    def create_kernel_spec(self, is_cython=False, **kwargs):
        """Create a kernel spec for our own kernels

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.main.ipyconsole
        # Before creating our kernel spec, we always need to
        # set this value in spyder.ini
        CONF.set('main', 'spyder_pythonpath',
                 ipycon.main.get_spyder_pythonpath())
        return MxKernelSpec(is_cython=is_cython, **kwargs)

    def create_kernel_manager_and_kernel_client(self, connection_file,
                                                stderr_handle,
                                                is_cython=False):
        return IPythonConsole.create_kernel_manager_and_kernel_client(
            self, connection_file, stderr_handle,
            is_cython=is_cython)

    def process_started(self, client):
        if spyder.version_info > (5, 1):
            # process_started is renamed
            # to shellwidget_started in Spyder 5.1
            self.main.ipyconsole.shellwidget_started(client)
        else:
            self.main.ipyconsole.process_started(client)
        self.add_shellwidget(client.shellwidget)
        if self.analyzer is not None:
            self.analyzer.add_shellwidget(client.shellwidget)
        if self.dataview is not None:
            self.dataview.add_shellwidget(client.shellwidget)

    def process_finished(self, client):
        if spyder.version_info > (5, 1):
            self.main.ipyconsole.shellwidget_deleted(client)
        else:
            # process_finished is renamed
            # to shellwidget_deleted in Spyder 5.1
            self.main.ipyconsole.process_finished(client)
        self.remove_shellwidget(id(client.shellwidget))
        if self.analyzer is not None:
            self.analyzer.remove_shellwidget(id(client.shellwidget))
        if self.dataview is not None:
            self.dataview.remove_shellwidget(id(client.shellwidget))

    def _create_client_for_kernel(self, connection_file, hostname, sshkey,
                                  password):
        ipycon = self.ipyconsole

        # Verifying if the connection file exists
        try:
            cf_path = osp.dirname(connection_file)
            cf_filename = osp.basename(connection_file)
            # To change a possible empty string to None
            cf_path = cf_path if cf_path else None
            connection_file = find_connection_file(filename=cf_filename,
                                                   path=cf_path)
        except (IOError, UnboundLocalError):
            QMessageBox.critical(self, _('IPython'),
                                 _("Unable to connect to "
                                   "<b>%s</b>") % connection_file)
            return

        # Getting the master id that corresponds to the client
        # (i.e. the i in i/A)
        master_id = None
        given_name = None
        external_kernel = False
        slave_ord = ord('A') - 1
        kernel_manager = None

        for cl in ipycon.get_clients():
            if connection_file in cl.connection_file:
                if cl.get_kernel() is not None:
                    kernel_manager = cl.get_kernel()
                connection_file = cl.connection_file
                if master_id is None:
                    master_id = cl.id_['int_id']
                given_name = cl.given_name
                new_slave_ord = ord(cl.id_['str_id'])
                if new_slave_ord > slave_ord:
                    slave_ord = new_slave_ord

        # If we couldn't find a client with the same connection file,
        # it means this is a new master client
        if master_id is None:
            ipycon.master_clients += 1
            master_id = to_text_string(ipycon.master_clients)
            external_kernel = True

        # Set full client name
        client_id = dict(int_id=master_id,
                         str_id=chr(slave_ord + 1))

        # Creating the client
        show_elapsed_time = ipycon.get_option('show_elapsed_time')
        reset_warning = ipycon.get_option('show_reset_namespace_warning')
        ask_before_restart = ipycon.get_option('ask_before_restart')
        client = MxClientWidget(ipycon,
                              id_=client_id,
                              given_name=given_name,
                              history_filename=get_conf_path('history.py'),
                              config_options=ipycon.config_options(),
                              additional_options=ipycon.additional_options(),
                              interpreter_versions=ipycon.interpreter_versions(),
                              connection_file=connection_file,
                              menu_actions=self.menu_actions,
                              hostname=hostname,
                              external_kernel=external_kernel,
                              slave=True,
                              show_elapsed_time=show_elapsed_time,
                              reset_warning=reset_warning,
                              ask_before_restart=ask_before_restart,
                              css_path=ipycon.css_path)

        # Change stderr_dir if requested
        if ipycon.test_dir is not None:
            client.stderr_dir = ipycon.test_dir

        # Create kernel client
        kernel_client = QtKernelClient(connection_file=connection_file)

        # This is needed for issue spyder-ide/spyder#9304.
        try:
            kernel_client.load_connection_file()
        except Exception as e:
            QMessageBox.critical(self, _('Connection error'),
                                 _("An error occurred while trying to load "
                                   "the kernel connection file. The error "
                                   "was:\n\n") + to_text_string(e))
            return

        if hostname is not None:
            try:
                connection_info = dict(ip = kernel_client.ip,
                                       shell_port = kernel_client.shell_port,
                                       iopub_port = kernel_client.iopub_port,
                                       stdin_port = kernel_client.stdin_port,
                                       hb_port = kernel_client.hb_port)
                newports = ipycon.tunnel_to_kernel(connection_info, hostname,
                                                 sshkey, password)
                (kernel_client.shell_port,
                 kernel_client.iopub_port,
                 kernel_client.stdin_port,
                 kernel_client.hb_port) = newports
                # Save parameters to connect comm later
                kernel_client.ssh_parameters = (hostname, sshkey, password)
            except Exception as e:
                QMessageBox.critical(self, _('Connection error'),
                                   _("Could not open ssh tunnel. The "
                                     "error was:\n\n") + to_text_string(e))
                return

        # Assign kernel manager and client to shellwidget
        kernel_client.start_channels()
        shellwidget = client.shellwidget
        shellwidget.set_kernel_client_and_manager(
            kernel_client, kernel_manager)
        shellwidget.sig_exception_occurred.connect(
            self.main.console.sig_exception_occurred)
        if external_kernel:
            shellwidget.sig_is_spykernel.connect(
                self.connect_external_kernel)
            shellwidget.check_spyder_kernel()

        # Set elapsed time, if possible
        if not external_kernel:
            ipycon.set_elapsed_time(client)

        # Adding a new tab for the client
        ipycon.add_tab(client, name=client.get_name())

        # Register client
        ipycon.register_client(client)

    def connect_external_kernel(self, shellwidget):
        """
        Connect an external kernel to the Variable Explorer, Help and
        Plots, but only if it is a Spyder kernel.
        """
        sw = shellwidget
        kc = shellwidget.kernel_client
        self.add_shellwidget(shellwidget)

        kc.stopped_channels.connect(lambda: self.remove_shellwidget(id(sw)))
        if self.analyzer is not None:
            self.analyzer.add_shellwidget(shellwidget)
            kc.stopped_channels.connect(lambda: self.analyzer.remove_shellwidget(id(sw)))
        if self.dataview is not None:
            self.dataview.add_shellwidget(shellwidget)
            kc.stopped_channels.connect(lambda: self.dataview.remove_shellwidget(id(sw)))

        self.ipyconsole.connect_external_kernel(shellwidget)


class ModelxConfigPage(PluginConfigPage):
    """modelx plugin preferences."""

    def get_name(self):
        return _('modelx')

    def setup_page(self):
        pass


class ModelxPlugin(SpyderDockablePlugin):
    """modelx plugin."""

    NAME = 'modelx_plugin'
    WIDGET_CLASS = MxPluginMainWidget
    REQUIRES = [Plugins.IPythonConsole]
    CONF_SECTION = 'modelx'
    CONFIGWIDGET_CLASS = ModelxConfigPage
    CONF_FILE = False

    # -------------------------------------------------------------------
    # --- API: Mandatory methods to define ------------------------------

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