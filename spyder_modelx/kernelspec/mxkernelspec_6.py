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

from spyder.plugins.ipythonconsole.utils.kernelspec import (
    SpyderKernelSpec,
    get_python_executable,
    is_conda_env,
    find_conda,
    get_conda_env_path,
    logger
)

# Modified from https://github.com/spyder-ide/spyder/blob/v6.0.4/spyder/plugins/ipythonconsole/utils/kernelspec.py#L79
class MxKernelSpec(SpyderKernelSpec):
    """Kernel spec for Spyder kernels"""

    CONF_SECTION = 'ipython_console'

    @property
    def argv(self):
        """Command to start kernels"""
        # Python interpreter used to start kernels
        if (
            self.get_conf('default', section='main_interpreter')
            and not self.path_to_custom_interpreter
        ):
            pyexec = get_python_executable()
        else:
            pyexec = self.get_conf('executable', section='main_interpreter')
            if self.path_to_custom_interpreter:
                pyexec = self.path_to_custom_interpreter
            if not has_spyder_kernels(pyexec):
                raise SpyderKernelError(
                    ERROR_SPYDER_KERNEL_INSTALLED.format(
                        pyexec,
                        SPYDER_KERNELS_VERSION,
                        SPYDER_KERNELS_CONDA,
                        SPYDER_KERNELS_PIP
                    )
                )
                return
            if not is_python_interpreter(pyexec):
                pyexec = get_python_executable()
                self.set_conf('executable', '', section='main_interpreter')
                self.set_conf('default', True, section='main_interpreter')
                self.set_conf('custom', False, section='main_interpreter')

        # Command used to start kernels
        kernel_cmd = []

        if is_conda_env(pyexec=pyexec):
            # If executable is a conda environment, use "run" subcommand to
            # activate it and run spyder-kernels.
            conda_exe = find_conda()

            kernel_cmd.extend([
                conda_exe,
                'run',
                '--prefix',
                get_conda_env_path(pyexec)
            ])

            # We need to use this flag to prevent conda_exe from capturing the
            # kernel process stdout/stderr streams. That way we are able to
            # show them in Spyder.
            if conda_exe.endswith(('micromamba', 'micromamba.exe')):
                kernel_cmd.extend(['--attach', '""'])
            else:
                # Note: We use --no-capture-output instead of --live-stream
                # here because it works for older Conda versions.
                kernel_cmd.append('--no-capture-output')

        kernel_cmd.extend([
            pyexec,
            # This is necessary to avoid a spurious message on Windows.
            # Fixes spyder-ide/spyder#20800.
            '-Xfrozen_modules=off',
            '-m', 'spymx_kernels.console',
            '-f', '{connection_file}'
        ])

        logger.info('Kernel command: {}'.format(kernel_cmd))

        return kernel_cmd


