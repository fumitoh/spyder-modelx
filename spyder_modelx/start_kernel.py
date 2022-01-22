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
import os.path
import spyder


def main():
    """Copied and modified from spyder.utils.ipython.start_kernel.py(v3.2.8)"""

    # Remove this module's path from sys.path:
    try:
        sys.path.remove(os.path.dirname(__file__))
    except ValueError:
        pass

    try:
        locals().pop('__file__')
    except KeyError:
        pass
    __doc__ = ''
    __name__ = '__main__'

    # Add current directory to sys.path (like for any standard Python interpreter
    # executed in interactive mode):
    sys.path.insert(0, '')

    if spyder.version_info >= (3, 3, 0):
        from spyder_kernels.console.start import import_spydercustomize
        # Import our customizations into the kernel
        import_spydercustomize()

    # Fire up the kernel instance.
    from ipykernel.kernelapp import IPKernelApp

    if spyder.version_info < (3, 3, 0):
        from spyder.utils.ipython.start_kernel import kernel_config, varexp
    else:
        from spyder_kernels.console.start import kernel_config, varexp

    from spyder_modelx.mxkernel import ModelxKernel


    kernel = IPKernelApp.instance()
    kernel.kernel_class = ModelxKernel
    try:
        kernel.config = kernel_config()
    except:
        pass
    kernel.initialize()

    # The comment below seems to be false for at least Spyder v3.3.2
    # __IPYTHON___ is indeed defined when modelx system is created.
    #
    # (Setup modelx for IPython here because
    # __IPYTHON__ is not defined before kernel.initialize())
    #
    # kernel.kernel.get_modelx().setup_ipython()

    # Set our own magics
    kernel.shell.register_magic_function(varexp)

    # Set Pdb class to be used by %debug and %pdb.
    # This makes IPython consoles to use the class defined in our
    # sitecustomize instead of their default one.
    import pdb
    kernel.shell.InteractiveTB.debugger_cls = pdb.Pdb

    # Start the (infinite) kernel event loop.
    kernel.start()


if __name__ == '__main__':
    main()
