import os.path as osp

from spyder.config.base import _, running_under_pytest
from spyder.api.preferences import PluginConfigPage
from spyder.api.plugin_registration.decorators import on_plugin_available

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
from spyder.plugins.ipythonconsole.widgets.main_widget import (
    IPythonConsoleWidgetOptionsMenuSections,
    SPYDER_KERNELS_VERSION,
    SPYDER_KERNELS_VERSION_MSG,
    SPYDER_KERNELS_CONDA,
    SPYDER_KERNELS_PIP
)

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

    sig_shellwidget_deleted = Signal(object)
    """
    This signal is emitted when a shellwidget is deleted/removed.

    Parameters
    ----------
    shellwidget: spyder.plugins.ipyconsole.widgets.shell.ShellWidget
        The shellwigdet.
    """

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
                          is_pylab=False, is_sympy=False, given_name=None):
        """Create a new client

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.ipyconsole

        ipycon.master_clients += 1
        client_id = dict(int_id=to_text_string(ipycon.master_clients),
                         str_id='A')
        cf = ipycon._new_connection_file()

        show_elapsed_time = ipycon.get_conf('show_elapsed_time')
        reset_warning = ipycon.get_conf('show_reset_namespace_warning')
        client_kwargs = {
            "ask_before_restart": ipycon.get_conf('ask_before_restart'),
            "ask_before_closing": ipycon.get_conf('ask_before_closing'),
            "css_path": ipycon.css_path,
            'handlers': ipycon.registered_spyder_kernel_handlers,
            'configuration': ipycon.CONFIGURATION
        }

        client = MxClientWidget(ipycon,
                                id_=client_id,
                                history_filename=get_conf_path('history.py'),
                                config_options=ipycon.config_options(),
                                additional_options=ipycon.additional_options(
                                    is_pylab=is_pylab,
                                    is_sympy=is_sympy),
                                interpreter_versions=ipycon.interpreter_versions(),
                                connection_file=cf,
                                # menu_actions=self.menu_actions,
                                show_elapsed_time=show_elapsed_time,
                                reset_warning=reset_warning,
                                **client_kwargs)

        ipycon.add_tab(client, name=client.get_name(), filename=filename, give_focus=give_focus)

        if cf is None:
            error_msg = ipycon.PERMISSION_ERROR_MSG.format(jupyter_runtime_dir())
            client.show_kernel_error(error_msg)
            return

        # Check if ipykernel is present in the external interpreter.
        # Else we won't be able to create a client
        if not ipycon.get_conf('default', section='main_interpreter'):
            pyexec = ipycon.get_conf('executable', section='main_interpreter')
            has_spyder_kernels = programs.is_module_installed(
                'spyder_kernels',
                interpreter=pyexec,
                version=SPYDER_KERNELS_VERSION)
            if not has_spyder_kernels and not running_under_pytest():
                client.show_kernel_error(
                    _("The Python environment or installation whose "
                      "interpreter is located at"
                      "<pre>"
                      "    <tt>{0}</tt>"
                      "</pre>"
                      "doesn't have the <tt>spyder-kernels</tt> module or the "
                      "right version of it installed ({1}). "
                      "Without this module is not possible for Spyder to "
                      "create a console for you.<br><br>"
                      "You can install it by activating your environment (if "
                      "necessary) and then running in a system terminal:"
                      "<pre>"
                      "    <tt>{2}</tt>"
                      "</pre>"
                      "or"
                      "<pre>"
                      "    <tt>{3}</tt>"
                      "</pre>").format(
                          pyexec,
                          SPYDER_KERNELS_VERSION_MSG,
                          SPYDER_KERNELS_CONDA,
                          SPYDER_KERNELS_PIP
                      )
                )
                return

        self.connect_client_to_kernel(client, is_cython=is_cython,
                                      is_pylab=is_pylab, is_sympy=is_sympy)
        if client.shellwidget.kernel_manager is None:
            return
        ipycon.register_client(client, give_focus=give_focus)

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
        ipycon = self.ipyconsole

        connection_file = client.connection_file
        stderr_handle = (
            None if ipycon._test_no_stderr else client.stderr_obj.handle)
        stdout_handle = (
            None if ipycon._test_no_stderr else client.stdout_obj.handle)
        km, kc = self.create_kernel_manager_and_kernel_client(
            connection_file,
            stderr_handle,
            stdout_handle,
            is_cython=is_cython,
            **kwargs)

        # An error occurred if this is True
        if isinstance(km, str) and kc is None:
            client.shellwidget.kernel_manager = None
            client.show_kernel_error(km)
            return

        # This avoids a recurrent, spurious NameError when running our
        # tests in our CIs
        if not ipycon._testing:
            kc.started_channels.connect(
                lambda c=client: self.process_started(c))
            kc.stopped_channels.connect(
                lambda c=client: self.process_finished(c))
        kc.start_channels(shell=True, iopub=True)

        shellwidget = client.shellwidget
        shellwidget.set_kernel_client_and_manager(kc, km)
        shellwidget.sig_exception_occurred.connect(
            self.sig_exception_occurred)

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
                                                stdout_handle,
                                                is_cython=False,
                                                **kwargs
                                                ):
        return IPythonConsole.WIDGET_CLASS.create_kernel_manager_and_kernel_client(
            self, connection_file, stderr_handle, stdout_handle,
            is_cython=is_cython, **kwargs)

    def process_started(self, client):

        # process_started is renamed
        # to shellwidget_started in Spyder 5.1
        self.ipyconsole._shellwidget_started(client)

        self.add_shellwidget(client.shellwidget)
        if self.analyzer is not None:
            self.analyzer.add_shellwidget(client.shellwidget)
        if self.dataview is not None:
            self.dataview.add_shellwidget(client.shellwidget)

    def process_finished(self, client):
        self.ipyconsole._shellwidget_deleted(client)

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
            if osp.splitext(connection_file)[1] != ".json":
                # There might be a file with the same id in the path.
                connection_file = find_connection_file(
                    filename=cf_filename + ".json", path=cf_path)
        except (IOError, UnboundLocalError):
            QMessageBox.critical(self, _('IPython'),
                                 _("Unable to connect to "
                                   "<b>%s</b>") % connection_file)
            return

        # Getting the master id that corresponds to the client
        # (i.e. the i in i/A)
        master_id = None
        given_name = None
        is_external_kernel = True
        known_spyder_kernel = False
        slave_ord = ord('A') - 1
        kernel_manager = None

        for cl in ipycon.clients:
            if connection_file in cl.connection_file:
                if cl.get_kernel() is not None:
                    kernel_manager = cl.get_kernel()
                connection_file = cl.connection_file
                if master_id is None:
                    master_id = cl.id_['int_id']
                    is_external_kernel = cl.shellwidget.is_external_kernel
                    known_spyder_kernel = cl.shellwidget.is_spyder_kernel
                given_name = cl.given_name
                new_slave_ord = ord(cl.id_['str_id'])
                if new_slave_ord > slave_ord:
                    slave_ord = new_slave_ord

        # If we couldn't find a client with the same connection file,
        # it means this is a new master client
        if master_id is None:
            ipycon.master_clients += 1
            master_id = str(ipycon.master_clients)

        # Set full client name
        client_id = dict(int_id=master_id,
                         str_id=chr(slave_ord + 1))

        # Creating the client
        show_elapsed_time = ipycon.get_conf('show_elapsed_time')
        reset_warning = ipycon.get_conf('show_reset_namespace_warning')
        ask_before_restart = ipycon.get_conf('ask_before_restart')
        client_args = {
            'ask_before_closing': ipycon.get_conf('ask_before_closing'),
            'std_dir': ipycon._test_dir if ipycon._test_dir else None,
            'is_external_kernel': is_external_kernel,
            'is_spyder_kernel': known_spyder_kernel,
            'handlers': ipycon.registered_spyder_kernel_handlers,
            'configuration': ipycon.CONFIGURATION
        }

        client = MxClientWidget(ipycon,
                              id_=client_id,
                              given_name=given_name,
                              history_filename=get_conf_path('history.py'),
                              config_options=ipycon.config_options(),
                              additional_options=ipycon.additional_options(),
                              interpreter_versions=ipycon.interpreter_versions(),
                              connection_file=connection_file,
                              # menu_actions=menu_actions,
                              hostname=hostname,
                              # slave=True,
                              show_elapsed_time=show_elapsed_time,
                              reset_warning=reset_warning,
                              ask_before_restart=ask_before_restart,
                              css_path=ipycon.css_path,
                              **client_args)

        # Create kernel client
        kernel_client = QtKernelClient(connection_file=connection_file)

        # This is needed for issue spyder-ide/spyder#9304.
        try:
            kernel_client.load_connection_file()
        except Exception as e:
            QMessageBox.critical(self, _('Connection error'),
                                 _("An error occurred while trying to load "
                                   "the kernel connection file. The error "
                                   "was:\n\n") + str(e))
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
                                     "error was:\n\n") + str(e))
                return

        # Assign kernel manager and client to shellwidget
        kernel_client.start_channels()
        shellwidget = client.shellwidget
        shellwidget.set_kernel_client_and_manager(
            kernel_client, kernel_manager)
        shellwidget.sig_exception_occurred.connect(
            ipycon.sig_exception_occurred)

        if not known_spyder_kernel:
            shellwidget.sig_is_spykernel.connect(
                self.connect_external_spyder_kernel)
            shellwidget.check_spyder_kernel()

        ipycon.sig_shellwidget_created.emit(shellwidget)

        # Modified from IPython code to remove modelx widgets
        # kernel_client.stopped_channels.connect(
        #     lambda: ipycon.sig_shellwidget_deleted.emit(shellwidget))
        kernel_client.stopped_channels.connect(
            lambda c=client: self.process_finished(c)
        )

        # Set elapsed time, if possible
        if not is_external_kernel:
            ipycon.set_client_elapsed_time(client)

        # Adding a new tab for the client
        ipycon.add_tab(client, name=client.get_name())

        # Register client
        ipycon.register_client(client)

    def connect_external_spyder_kernel(self, shellwidget):
        """
        Connect an external kernel to the Variable Explorer, Help and
        Plots, but only if it is a Spyder kernel.
        """
        self.add_shellwidget(shellwidget)
        if self.analyzer is not None:
            self.analyzer.add_shellwidget(shellwidget)
        if self.dataview is not None:
            self.dataview.add_shellwidget(shellwidget)
        self.ipyconsole.connect_external_spyder_kernel(shellwidget)


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
