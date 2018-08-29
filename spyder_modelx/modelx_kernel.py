import modelx as mx
import spyder

if spyder.version_info < (3, 3, 0):
    from spyder.utils.ipython.spyder_kernel import SpyderKernel
else:
    from spyder_kernels.console.kernel import SpyderKernel

class ModelxKernel(SpyderKernel):

    def mx_get_models(self):
        return repr(mx.cur_model().literaldict)
