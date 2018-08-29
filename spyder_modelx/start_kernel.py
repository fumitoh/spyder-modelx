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

    from spyder_modelx.modelx_kernel import ModelxKernel


    kernel = IPKernelApp.instance()
    kernel.kernel_class = ModelxKernel
    try:
        kernel.config = kernel_config()
    except:
        pass
    kernel.initialize()

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
