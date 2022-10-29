import os.path as osp

import spyder
from spyder.config.base import _, running_under_pytest

from jupyter_client.connect import find_connection_file
from jupyter_core.paths import jupyter_config_dir, jupyter_runtime_dir
from qtconsole.client import QtKernelClient

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import (QMessageBox)

from spyder.config.base import DEV, get_conf_path, get_home_dir, get_module_path
from spyder.py3compat import is_string, PY2, to_text_string

from spyder.config.manager import CONF
from spyder.utils import encoding, programs, sourcecode

from spyder.plugins.ipythonconsole.plugin import IPythonConsole
from spyder.plugins.ipythonconsole.widgets import KernelConnectionDialog
from spyder.plugins.ipythonconsole.widgets.main_widget import (
    IPythonConsoleWidgetOptionsMenuSections,
    SPYDER_KERNELS_VERSION,
    SPYDER_KERNELS_VERSION_MSG,
    SPYDER_KERNELS_CONDA,
    SPYDER_KERNELS_PIP
)
from spyder.plugins.ipythonconsole.utils.stdfile import StdFile

from spyder_modelx.mxkernelspec import MxKernelSpec
from spyder_modelx.widgets.mxclient import MxClientWidget_5_3 as MxClientWidget


class MxConsoleAPI_5_3:

    sig_shellwidget_deleted = Signal(object)

    @Slot()
    @Slot(bool)
    @Slot(str)
    @Slot(bool, str)
    @Slot(bool, bool)
    @Slot(bool, str, bool)
    def create_new_client(self, give_focus=True, filename='', is_cython=False,
                          is_pylab=False, is_sympy=False, given_name=None,
                          initial_cwd=None  # 5.3.3-
                          ):
        """Create a new client

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.ipyconsole

        ipycon.master_clients += 1
        client_id = dict(int_id=to_text_string(ipycon.master_clients),
                         str_id='A')
        std_dir = ipycon._test_dir if ipycon._test_dir else None
        cf, km, kc, stderr_obj, stdout_obj = self.get_new_kernel(
            is_cython, is_pylab, is_sympy, std_dir=std_dir)

        if cf is not None:
            fault_obj = StdFile(cf, '.fault', std_dir)
        else:
            fault_obj = None

        show_elapsed_time = ipycon.get_conf('show_elapsed_time')
        reset_warning = ipycon.get_conf('show_reset_namespace_warning')
        client_kwargs = {
            "ask_before_restart": ipycon.get_conf('ask_before_restart'),
            "ask_before_closing": ipycon.get_conf('ask_before_closing'),
            "css_path": ipycon.css_path,
            'handlers': ipycon.registered_spyder_kernel_handlers,
            'stderr_obj': stderr_obj,
            'stdout_obj': stdout_obj,
            'fault_obj': fault_obj,
            'initial_cwd': initial_cwd  # 5.3.3-
        }
        if spyder.version_info < (5, 2):
            client_kwargs['configuration'] = ipycon.CONFIGURATION

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

        self.connect_client_to_kernel(client, km, kc)

        if client.shellwidget.kernel_manager is None:
            return
        ipycon.register_client(client, give_focus=give_focus)
        return client   # 5.3.3

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

    def get_new_kernel(self, is_cython=False, is_pylab=False,
                       is_sympy=False, std_dir=None):
        """Get a new kernel, and cache one for next time."""
        # Cache another kernel for next time.
        ipycon = self.ipyconsole
        kernel_spec = self.create_kernel_spec(
            is_cython=is_cython,
            is_pylab=is_pylab,
            is_sympy=is_sympy
        )

        new_kernel = self.create_new_kernel(kernel_spec, std_dir)
        if new_kernel[2] is None:
            # error
            ipycon.close_cached_kernel()
            return new_kernel

        # Check cached kernel has the same configuration as is being asked
        cached_kernel = None
        if ipycon._cached_kernel_properties is not None:
            (cached_spec,
             cached_env,
             cached_argv,
             cached_dir,
             cached_kernel) = ipycon._cached_kernel_properties
            # Call interrupt_mode so the dict will be the same
            kernel_spec.interrupt_mode
            cached_spec.interrupt_mode
            valid = (std_dir == cached_dir
                     and cached_spec.__dict__ == kernel_spec.__dict__
                     and kernel_spec.argv == cached_argv
                     and kernel_spec.env == cached_env)
            if not valid:
                # Close the kernel
                ipycon.close_cached_kernel()
                cached_kernel = None

        # Cache the new kernel
        ipycon._cached_kernel_properties = (
            kernel_spec,
            kernel_spec.env,
            kernel_spec.argv,
            std_dir,
            new_kernel)

        if cached_kernel is None:
            return self.create_new_kernel(kernel_spec, std_dir)

        return cached_kernel

    def create_new_kernel(self, kernel_spec, std_dir=None):
        """Create a new kernel."""
        connection_file = self.ipyconsole._new_connection_file()
        if connection_file is None:
            return None, None, None, None, None

        stderr_obj = None
        stderr_handle = None
        stdout_obj = None
        stdout_handle = None
        if not self.ipyconsole._test_no_stderr:
            stderr_obj = StdFile(connection_file, '.stderr', std_dir)
            stderr_handle = stderr_obj.handle
            stdout_obj = StdFile(connection_file, '.stdout', std_dir)
            stdout_handle = stdout_obj.handle

        km, kc = self.ipyconsole.create_kernel_manager_and_kernel_client(
            connection_file,
            stderr_handle,
            stdout_handle,
            kernel_spec,
        )
        return connection_file, km, kc, stderr_obj, stdout_obj

    def connect_client_to_kernel(self, client, km, kc):
        """Connect a client to its kernel

        Copied and modified from spyder.plugins.ipythonconsole.IPythonConsole
        """
        ipycon = self.ipyconsole

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
        stderr_obj = None
        stdout_obj = None
        fault_obj = None

        for cl in ipycon.clients:
            if connection_file in cl.connection_file:
                if cl.get_kernel() is not None:
                    kernel_manager = cl.get_kernel()
                connection_file = cl.connection_file
                if master_id is None:
                    master_id = cl.id_['int_id']
                    is_external_kernel = cl.shellwidget.is_external_kernel
                    known_spyder_kernel = cl.shellwidget.is_spyder_kernel
                    if cl.stderr_obj:
                        stderr_obj = cl.stderr_obj.copy()
                    if cl.stdout_obj:
                        stdout_obj = cl.stdout_obj.copy()
                    if cl.fault_obj:
                        fault_obj = cl.fault_obj.copy()
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
            'is_external_kernel': is_external_kernel,
            'is_spyder_kernel': known_spyder_kernel,
            'handlers': ipycon.registered_spyder_kernel_handlers,
            'stderr_obj': stderr_obj,
            'stdout_obj': stdout_obj,
            'fault_obj': fault_obj
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

