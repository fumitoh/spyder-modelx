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
import os
import os.path as osp

import spyder
from spyder.plugins.ipythonconsole.utils.kernelspec import SpyderKernelSpec
from spyder.utils.misc import get_python_executable
from spyder.utils.programs import is_python_interpreter

if spyder.version_info < (5,):
    from spyder.config.manager import CONF

if spyder.version_info > (4, 1):    # 4.1.0 onwards
    from spyder.plugins.ipythonconsole.utils.kernelspec import get_activation_script
    import logging
    logger = logging.getLogger(__name__)
    from spyder.utils.conda import (add_quotes, get_conda_activation_script,
                                    get_conda_env_path, is_conda_env)

if spyder.version_info >= (4, 1, 1):  # 4.1.1 onwards
    from spyder.plugins.ipythonconsole.utils.kernelspec import is_different_interpreter


class MxKernelSpec(SpyderKernelSpec):

    CONF_SECTION = 'ipython_console'    # 5.1.0 onwards

    @property
    def argv(self):
        """Command to start kernels"""
        # Python interpreter used to start kernels
        if spyder.version_info < (5, 1):
            if CONF.get('main_interpreter', 'default'):
                pyexec = get_python_executable()
            else:
                if spyder.version_info < (4, 2):
                    # Avoid IPython adding the virtualenv on which Spyder is running
                    # to the kernel sys.path
                    os.environ.pop('VIRTUAL_ENV', None)
                pyexec = CONF.get('main_interpreter', 'executable')
                if not is_python_interpreter(pyexec):
                    pyexec = get_python_executable()
                    CONF.set('main_interpreter', 'executable', '')
                    CONF.set('main_interpreter', 'default', True)
                    CONF.set('main_interpreter', 'custom', False)
        else:
            if self.get_conf('default', section='main_interpreter'):
                pyexec = get_python_executable()
            else:
                pyexec = self.get_conf('executable', section='main_interpreter')
                if not is_python_interpreter(pyexec):
                    pyexec = get_python_executable()
                    self.set_conf('executable', '', section='main_interpreter')
                    self.set_conf('default', True, section='main_interpreter')
                    self.set_conf('custom', False, section='main_interpreter')

        if spyder.version_info <= (4, 1, 1):
            # Fixes spyder-ide/spyder#3427.
            if os.name == 'nt':
                dir_pyexec = osp.dirname(pyexec)
                pyexec_w = osp.join(dir_pyexec, 'pythonw.exe')
                if osp.isfile(pyexec_w):
                    pyexec = pyexec_w

        # Command used to start kernels
        if spyder.version_info < (4, 1):    # 4.0.x
            kernel_cmd = [
                pyexec,
                '-m',
                'spymx_kernels.start_kernel',
                '-f',
                '{connection_file}'
            ]
        else:
            if spyder.version_info == (4, 1, 1):
                is_different = False    # pyexec != sys.executable
            else:
                # Part of spyder-ide/spyder#11819
                is_different = is_different_interpreter(pyexec)

            if is_different and is_conda_env(pyexec=pyexec):
                # If this is a conda environment we need to call an intermediate
                # activation script to correctly activate the spyder-kernel
                # If changes are needed on this section make sure you also update
                # the activation scripts at spyder/plugins/ipythonconsole/scripts/

                if spyder.version_info < (4, 2):
                    conda_activation_script = get_conda_activation_script()
                else:
                    conda_activation_script = get_conda_activation_script(pyexec)

                kernel_cmd = [
                    get_activation_script(),  # This is bundled with Spyder
                    conda_activation_script,
                    get_conda_env_path(pyexec),  # Might be external
                    pyexec,
                    '{connection_file}',
                ]
            else:
                kernel_cmd = [
                    pyexec,
                    '-m',
                    'spymx_kernels.start_kernel',
                    '-f',
                    '{connection_file}'
                ]
            logger.info('Kernel command: {}'.format(kernel_cmd))

        return kernel_cmd


