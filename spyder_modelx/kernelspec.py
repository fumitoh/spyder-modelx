
import os.path

import spyder
from spyder.utils.ipython.kernelspec import SpyderKernelSpec


class ModelxKernelSpec(SpyderKernelSpec):

    @property
    def argv(self):

        kernel_cmd = SpyderKernelSpec.argv.fget(self)

        if spyder.version_info < (3, 3, 0):
            here = os.path.abspath(os.path.dirname(__file__))
            kernel_cmd[1] = os.path.join("%s" % here, "start_kernel.py")
        else:
            kernel_cmd[2] = 'spyder_modelx.start_kernel'

        return kernel_cmd



