
from spyder.config.base import _
from spyder.api.preferences import PluginConfigPage

from jupyter_core.paths import jupyter_config_dir, jupyter_runtime_dir

from spyder.api.plugins import SpyderPluginWidget

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel,
                            QSplitter, QStackedWidget)
import spyder

from spyder.config.base import DEV, get_conf_path, get_home_dir, get_module_path
from spyder.utils import icon_manager as ima
from spyder.py3compat import is_string, PY2, to_text_string

from spyder.config.manager import CONF
from spyder.utils import encoding, programs, sourcecode
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, create_plugin_layout)
from spyder.plugins.ipythonconsole.plugin import IPythonConsole

from spyder_modelx.mxkernelspec import MxKernelSpec
from spyder_modelx.widgets.mxexplorer import MxMainWidget
from spyder_modelx.widgets.mxclient import MxClientWidget

from .stacked_mixin import MxStackedMixin
from .dataview_plugin import MxDataViewPlugin
from .analyzer_plugin import MxAnalyzerPlugin


class ModelxConfigPage(PluginConfigPage):
    """modelx plugin preferences."""

    def get_name(self):
        return _('modelx')

    def setup_page(self):
        pass


class ModelxPlugin(MxStackedMixin, SpyderPluginWidget):
    """modelx plugin."""

    CONF_SECTION = 'modelx'
    CONFIGWIDGET_CLASS = ModelxConfigPage
    MX_WIDGET_CLASS = MxMainWidget
    CONF_FILE = False

    def __init__(self, parent=None, testing=False):
        SpyderPluginWidget.__init__(self, parent)
        MxStackedMixin.__init__(self, parent)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.options_button.setVisible(False)
        self.setLayout(layout)

    # --- SpyderPluginWidget API ----------------------------------------------
    def get_plugin_title(self):
        """Return widget title."""
        return _('MxExplorer')

    def get_focus_widget(self):
        """Return the widget to give focus to."""
        return self.current_widget()

    def refresh_plugin(self):
        """Refresh MxExplorer widget."""
        pass

    def get_plugin_actions(self):
        """Return a list of actions related to plugin.

        Note: these actions will be enabled when plugin's dockwidget is visible
              and they will be disabled when it's hidden
        """

        create_client_action = create_action(
            self,
            _("New MxConsole"),
            icon=ima.icon('ipython_console'),
            triggered=self.create_new_client,
            context=Qt.WidgetWithChildrenShortcut)
        self.register_shortcut(create_client_action, context="ipython_console",
                               name="New tab")

        # Add the action to the 'Consoles' menu on the main window
        main_consoles_menu = self.main.consoles_menu_actions
        main_consoles_menu.insert(0, create_client_action)
        self.main.ipyconsole.menu_actions.insert(0, create_client_action)

        # Plugin actions
        self.menu_actions = [create_client_action] + \
                            self.main.ipyconsole.menu_actions.copy()

        add_actions(self.main.ipyconsole.tabwidget.menu,
                    [create_client_action],
                    insert_before=main_consoles_menu[1])

        # This should return the actions specific to this plugin.
        return [create_client_action]

    def register_plugin(self):
        """Register plugin in Spyder's main window."""
        self.add_dockwidget()
        self.register_subplugin()

    def register_subplugin(self):
        """Register sub plugin """
        self.dataview = MxDataViewPlugin(self.main)
        self.main.thirdparty_plugins.append(self.dataview)
        self.dataview.register_plugin()

        self.analyzer = MxAnalyzerPlugin(self.main)
        self.main.thirdparty_plugins.append(self.analyzer)
        self.analyzer.register_plugin()

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
    def create_new_client(self, give_focus=True, filename='', is_cython=False,
                          **kwargs):
        """Create a new client

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.main.ipyconsole

        ipycon.master_clients += 1
        client_id = dict(int_id=to_text_string(ipycon.master_clients),
                         str_id='A')
        cf = ipycon._new_connection_file()
        show_elapsed_time = ipycon.get_option('show_elapsed_time')
        reset_warning = ipycon.get_option('show_reset_namespace_warning')
        client_kwargs = {
            "ask_before_restart": ipycon.get_option('ask_before_restart'),
            "options_button": ipycon.options_button,
            "css_path": ipycon.css_path
        }
        if spyder.version_info > (4, 2, 0):
            client_kwargs["ask_before_closing"] = ipycon.get_option('ask_before_closing')
        if "given_name" in kwargs:
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
            self.main.console.exception_occurred)

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
        self.main.ipyconsole.process_started(client)
        self.add_shellwidget(client.shellwidget)
        if self.analyzer is not None:
            self.analyzer.add_shellwidget(client.shellwidget)
        if self.dataview is not None:
            self.dataview.add_shellwidget(client.shellwidget)

    def process_finished(self, client):
        self.main.ipyconsole.process_finished(client)
        self.remove_shellwidget(id(client.shellwidget))
        if self.analyzer is not None:
            self.analyzer.remove_shellwidget(id(client.shellwidget))
        if self.dataview is not None:
            self.dataview.remove_shellwidget(id(client.shellwidget))
