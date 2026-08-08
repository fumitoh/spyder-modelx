import functools
import os.path as osp

import spyder
from spyder.config.base import _, running_under_pytest

from jupyter_client.connect import find_connection_file
from jupyter_core.paths import jupyter_config_dir, jupyter_runtime_dir
from qtconsole.client import QtKernelClient

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import (QMessageBox)

from spyder.config.base import DEV, get_conf_path, get_home_dir, get_module_path

from spyder.config.manager import CONF
from spyder.utils import encoding, programs, sourcecode

from spyder.api.asyncdispatcher import AsyncDispatcher
from spyder.plugins.ipythonconsole.plugin import IPythonConsole
from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler
from spyder.plugins.ipythonconsole.widgets import KernelConnectionDialog
from spyder.utils.environ import get_user_environment_variables

from spyder_modelx.kernelspec import MxKernelSpec
from spyder_modelx.widgets.mxclient import MxClientWidget_6_0 as MxClientWidget


def _kernel_env_must_be_set():
    """Whether the caller must fill in the kernel spec's environment.

    Up to Spyder 6.1.0, ``SpyderKernelSpec.env`` was a computed property that
    merged ``os.environ`` itself, so a spec that was never assigned an ``env``
    still reported a complete environment. Spyder 6.1.1 moved that merge into
    the ``env`` setter (spyder-ide/spyder#23761), which means a spec whose
    ``env`` is never assigned now reports an empty dict and the kernel gets
    launched with no environment variables at all.

    Detect the setter instead of pinning a Spyder version: on 6.0.x ``env`` is
    read-only and assigning to it would raise, while on 6.1.0 assigning is
    harmless and is what Spyder itself does.

    ``MxKernelSpec`` is inspected rather than ``SpyderKernelSpec`` because it is
    the class actually assigned to below, so this stays correct even if
    ``MxKernelSpec`` ever overrides ``env`` itself.
    """
    for klass in MxKernelSpec.__mro__:
        if 'env' in klass.__dict__:
            prop = klass.__dict__['env']
            return isinstance(prop, property) and prop.fset is not None
    return False


class MxConsoleAPI_6_0:


    # Modified from create_new_client at
    # https://github.com/spyder-ide/spyder/blob/v6.0.4/spyder/plugins/ipythonconsole/widgets/main_widget.py#L1699
    @Slot()
    @Slot(bool)
    @Slot(str)
    @Slot(bool, str)
    @Slot(bool, str, str)
    @Slot(bool, bool)
    @Slot(bool, str, bool)
    def create_new_client(self, give_focus=True, filename='', special=None,
                          given_name='MxConsole', cache=True, initial_cwd=None,
                          path_to_custom_interpreter=None):
        """Create a new client"""

        ipycon = self.ipyconsole

        ipycon.master_clients += 1
        client_id = dict(int_id=str(ipycon.master_clients),
                         str_id='A')

        # Find what kind of kernel we want
        if ipycon.get_conf('pylab/autoload'):
            special = "pylab"
        elif ipycon.get_conf('symbolic_math'):
            special = "sympy"

        client = MxClientWidget(
            ipycon,
            id_=client_id,
            config_options=ipycon.config_options(),
            additional_options=ipycon.additional_options(special),
            given_name=given_name,
            give_focus=give_focus,
            handlers=ipycon.registered_spyder_kernel_handlers,
            initial_cwd=initial_cwd,
            forcing_custom_interpreter=path_to_custom_interpreter is not None,
            special_kernel=special
        )

        future = None
        if _kernel_env_must_be_set():
            # Get the environment variables asynchronously and connect the
            # kernel once they are available, as create_new_client in Spyder's
            # IPythonConsoleWidget does.
            future = get_user_environment_variables()
            future.connect(
                AsyncDispatcher.QtSlot(
                    functools.partial(
                        self._connect_new_client_to_kernel,
                        cache,
                        path_to_custom_interpreter,
                        client,
                    )
                )
            )

        # Add client to widget
        ipycon.add_tab(
            client, name=client.get_name(), filename=filename,
            give_focus=give_focus)

        if future is None:
            self._connect_new_client_to_kernel(
                cache, path_to_custom_interpreter, client)

        return client

    def _connect_new_client_to_kernel(self, cache, path_to_custom_interpreter,
                                      client, future=None):
        """Connect kernel to client after environment variables are obtained"""
        ipycon = self.ipyconsole

        try:
            # Create new kernel
            kernel_spec = MxKernelSpec(
                path_to_custom_interpreter=path_to_custom_interpreter
            )
            if future is not None:
                kernel_spec.env = future.result()
            kernel_handler = ipycon.get_cached_kernel(kernel_spec, cache=cache)
        except Exception as e:
            client.show_kernel_error(e)
            return

        # Connect kernel to client
        client.connect_kernel(kernel_handler)


    # Modified from create_client_for_kernel at
    # https://github.com/spyder-ide/spyder/blob/v6.1.4/spyder/plugins/ipythonconsole/widgets/main_widget.py#L1846
    def create_client_for_kernel(
        self,
        connection_file,
        hostname,
        sshkey,
        password,
        server_id=None,     # mx_change: Removed from Spyder 6.1.x
        jupyter_api=None,   # mx_change: Added in Spyder 6.1.x
        files_api=None,     # mx_change: Added in Spyder 6.1.x
        give_focus=False,
        can_close=True
    ):
        """Create a client connected to an existing kernel."""

        ipycon = self.ipyconsole
        given_name = None
        master_client = None

        related_clients = []
        for cl in ipycon.clients:
            if cl.connection_file and connection_file in cl.connection_file:
                if (
                    cl.kernel_handler is not None and
                    hostname == cl.kernel_handler.hostname and
                    sshkey == cl.kernel_handler.sshkey and
                    password == cl.kernel_handler.password
                ):
                    related_clients.append(cl)

        if len(related_clients) > 0:
            # Get master client
            master_client = related_clients[0]
            given_name = master_client.given_name
            slave_ord = ord('A') - 1
            for cl in related_clients:
                new_slave_ord = ord(cl.id_['str_id'])
                if new_slave_ord > slave_ord:
                    slave_ord = new_slave_ord

            # Set full client name
            client_id = dict(int_id=master_client.id_['int_id'],
                             str_id=chr(slave_ord + 1))
        else:
            # If we couldn't find a client with the same connection file,
            # it means this is a new master client
            ipycon.master_clients += 1

            # Set full client name
            client_id = dict(int_id=str(ipycon.master_clients), str_id='A')

        # Creating the client
        client = MxClientWidget(
            ipycon,
            id_=client_id,
            given_name=given_name,
            config_options=ipycon.config_options(),
            additional_options=ipycon.additional_options(),
            handlers=ipycon.registered_spyder_kernel_handlers,
            server_id=server_id,        # mx_change: Removed from Spyder 6.1.x
            jupyter_api=jupyter_api,    # mx_change: Added in Spyder 6.1.x
            files_api=files_api,        # mx_change: Added in Spyder 6.1.x
            give_focus=give_focus,
            can_close=can_close,
        )

        # add hostname for get_name
        client.hostname = hostname

        # Adding a new tab for the client
        ipycon.add_tab(client, name=client.get_name())

        # Set elapsed time, if possible
        if master_client is not None:
            client.t0 = master_client.t0
            client.timer.timeout.connect(client.show_time)
            client.timer.start(1000)
            client.timer.timeout.emit()

        # mx_change: is_remote checks server_id on Spyder 6.0.x and
        # jupyter_api on 6.1.x, so it stands for both versions of the test.
        if client.is_remote():
            # This is a client created by the RemoteClient plugin. So, we only
            # create the client and show it as loading because the kernel
            # connection part will be done by that plugin.
            client._show_loading_page()
        else:
            try:
                # Get new client for kernel
                if master_client is not None:
                    kernel_handler = master_client.kernel_handler.copy()
                else:
                    kernel_handler = KernelHandler.from_connection_file(
                        connection_file, hostname, sshkey, password)
            except Exception as e:
                client.show_kernel_error(e)
                return

            # Connect kernel
            client.connect_kernel(kernel_handler)

        return client

    @Slot()
    def _create_client_for_kernel(self):
        """Create a client connected to an existing kernel"""
        ipycon = self.ipyconsole

        connect_output = KernelConnectionDialog.get_connection_parameters(ipycon)
        (connection_file, hostname, sshkey, password, ok) = connect_output
        if not ok:
            return

        try:
            # Fix path
            connection_file = ipycon.find_connection_file(connection_file)
        except (IOError, UnboundLocalError):
            QMessageBox.critical(ipycon, _('IPython'),
                                 _("Unable to connect to "
                                   "<b>%s</b>") % connection_file)
            return

        # mx_change: Call our own create_client_for_kernel, not the one of the
        # IPython console, so that an MxClientWidget is created and the modelx
        # panes are connected to the kernel.
        self.create_client_for_kernel(
            connection_file, hostname, sshkey, password)
