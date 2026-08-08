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

from spyder.plugins.ipythonconsole.utils.kernelspec import SpyderKernelSpec

# The module started by the kernel command. Spyder starts its own kernels
# with SPYDER_KERNELS_MODULE and modelx replaces it with MX_KERNELS_MODULE.
SPYDER_KERNELS_MODULE = 'spyder_kernels.console'
MX_KERNELS_MODULE = 'spymx_kernels.console'


class MxKernelSpec(SpyderKernelSpec):
    """Kernel spec for modelx kernels"""

    CONF_SECTION = 'ipython_console'

    @property
    def argv(self):
        """Command to start kernels

        This delegates to ``SpyderKernelSpec.argv`` and only swaps the module
        started by the interpreter, so that interpreter detection and
        environment activation (conda, mamba, pixi, ...) never drift from
        Spyder's own implementation.

        See https://github.com/fumitoh/spyder-modelx/issues/45
        """
        return [
            MX_KERNELS_MODULE if arg == SPYDER_KERNELS_MODULE else arg
            for arg in super().argv
        ]

