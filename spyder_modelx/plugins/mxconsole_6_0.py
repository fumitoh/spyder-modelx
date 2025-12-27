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

from spyder.plugins.ipythonconsole.plugin import IPythonConsole
from spyder.plugins.ipythonconsole.widgets import KernelConnectionDialog

from spyder_modelx.kernelspec import MxKernelSpec
from spyder_modelx.widgets.mxclient import MxClientWidget_6_0 as MxClientWidget


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

        # Add client to widget
        ipycon.add_tab(
            client, name=client.get_name(), filename=filename,
            give_focus=give_focus)

        try:
            # Create new kernel
            kernel_spec = MxKernelSpec(
                path_to_custom_interpreter=path_to_custom_interpreter
            )
            kernel_handler = ipycon.get_cached_kernel(kernel_spec, cache=cache)
        except Exception as e:
            client.show_kernel_error(e)
            return

        # Connect kernel to client
        client.connect_kernel(kernel_handler)
        return client


    def create_client_for_kernel(self, connection_file, hostname, sshkey,
                                 password, server_id=None, give_focus=False,
                                 can_close=True):
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
            server_id=server_id,
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

        if server_id:
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

        ipycon.create_client_for_kernel(
            connection_file, hostname, sshkey, password)