# -*- coding: utf-8 -*-

# Copyright (c) 2017-2018 Fumito Hamamura <fumito.ham@gmail.com>

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

import spyder

if spyder.version_info < (3, 3, 0):
    from spyder.utils.ipython.spyder_kernel import SpyderKernel
else:
    from spyder_kernels.console.kernel import SpyderKernel


class ModelxKernel(SpyderKernel):

    def __init__(self, *args, **kwargs):
        super(ModelxKernel, self).__init__(*args, **kwargs)

    def get_modelx(self):
        from modelx.core import mxsys
        return mxsys

    def mx_get_models(self):
        import modelx as mx
        return repr(mx.cur_model()._baseattrs)

    def mx_get_codelist(self, fullname):
        import modelx as mx

        try:
            obj = mx.get_object(fullname)
            data = obj._to_attrdict(['formula'])
        except:
            data = None

        self.send_modelx_msg('codelist', data=data)

    def mx_get_evalresult(self, msgtype, frame):

        # The code below is based on SpyderKernel.get_value
        try:
            self.send_modelx_msg(msgtype, data=frame)
        except:
            # * There is no need to inform users about
            #   these errors.
            # * value = None makes Spyder to ignore
            #   petitions to display a value
            self.send_modelx_msg(msgtype, data=None)

        self._do_publish_pdb_state = False

    def send_modelx_msg(self, modelx_msg_type, content=None, data=None):
        """
        Publish custom messages to the Spyder frontend.

        This code is modified from send_spyder_msg in spyder-kernel v0.2.4

        Parameters
        ----------

        modelx_msg_type: str
            The spyder message type
        content: dict
            The (JSONable) content of the message
        data: any
            Any object that is serializable by cloudpickle (should be most
            things). Will arrive as cloudpickled bytes in `.buffers[0]`.
        """
        import cloudpickle

        if content is None:
            content = {}
        content['mx_msgtype'] = modelx_msg_type
        self.session.send(
            self.iopub_socket,
            'modelx_msg',
            content=content,
            buffers=[cloudpickle.dumps(data, protocol=2)],
            parent=self._parent_header)

