# -*- coding: utf-8 -*-

# Copyright (c) 2018-2019 Fumito Hamamura <fumito.ham@gmail.com>

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

import json
import spyder

if spyder.version_info < (3, 3, 0):
    from spyder.utils.ipython.spyder_kernel import SpyderKernel
else:
    from spyder_kernels.console.kernel import SpyderKernel

from spyder_modelx.util import hinted_tuple_hook


class ModelxKernel(SpyderKernel):

    def __init__(self, *args, **kwargs):
        super(ModelxKernel, self).__init__(*args, **kwargs)

        if spyder.version_info > (4,):

            for call_id, handler in [
                ('mx_get_modellist', self.mx_get_modellist),
                ('mx_get_adjacent', self.mx_get_adjacent),
                ('mx_new_model', self.mx_new_model),
                ('mx_read_model', self.mx_read_model),
                ('mx_del_object', self.mx_del_object),
                ('mx_del_model', self.mx_del_model),
                ('mx_write_model', self.mx_write_model)

            ]:
                self.frontend_comm.register_call_handler(
                    call_id,
                    handler
                )

    def get_modelx(self):
        from modelx.core import mxsys
        return mxsys

    def mx_new_model(self, name=None, define_var=False, varname=''):
        import modelx as mx
        model = mx.new_model(name)
        self._define_var(define_var, model, varname)
        self.send_mx_msg("mxupdated")

    def mx_read_model(self, modelpath, name, define_var, varname):
        import modelx as mx
        model = mx.read_model(modelpath, name)
        self._define_var(define_var, model, varname)
        self.send_mx_msg("mxupdated")

    def mx_write_model(self, model, modelpath, backup):
        import modelx as mx
        mx.write_model(mx.get_models()[model], modelpath, backup)

    def mx_new_space(self, model, parent, name, bases, define_var, varname):
        import modelx as mx

        model = self._get_or_create_model(model)

        if parent:
            parent = mx.get_object(parent)
        else:
            parent = model

        if not name:
            name = None

        if bases:
            bases = [model._get_from_name(b.strip()) for b in bases.split(",")]
        else:
            bases = None

        space = parent.new_space(name=name, bases=bases)
        self._define_var(define_var, space, varname)

        self.send_mx_msg("mxupdated")

    def mx_del_object(self, parent, name):
        import modelx as mx
        mx.get_object(parent).__delattr__(name)
        self.send_mx_msg("mxupdated")

    def mx_del_model(self, name):
        import modelx as mx
        mx.get_models()[name].close()
        self.send_mx_msg("mxupdated")

    def _define_var(self, define_var, obj, varname):
        if define_var:
            if varname:
                self._mglobals()[varname] = obj
            else:
                self._mglobals()[obj.name] = obj

    def mx_new_cells(self, model, parent, name, define_var, varname):
        """
        If name is blank and formula is blank, cells is auto-named.
        If name is blank and formula is func def, name is func name.
        If name is given and formula is blank, formula is lambda: None.
        If name is given and formula is given, formula is renamed to given name.

        Args:
            model: model name or blank
            parent: parent named id or blank
            name: cells name or blank
            formula: function def or lambda expression blank
        """
        model = self._get_or_create_model(model)
        if parent:
            parent = model._get_from_name(parent)
        else:
            parent = model.cur_space() if model.cur_space() else model.new_space()

        if not name:
            name = None

        ns = self._mglobals()
        if "__mx_temp" in ns:
            formula = ns["__mx_temp"]
            del ns["__mx_temp"]
        else:
            formula = None

        cells = parent.new_cells(
            name=name,
            formula=formula
        )
        self._define_var(define_var,cells, varname)
        self.send_mx_msg("mxupdated")

    def mx_set_formula(self, fullname):
        import modelx as mx

        obj = mx.get_object(fullname)
        ns = self._mglobals()
        if "__mx_temp" in ns:
            formula = ns["__mx_temp"]
            del ns["__mx_temp"]
        else:
            formula = None

        obj.set_formula(formula)
        self.send_mx_msg("mxupdated")

    def _get_or_create_model(self, model):
        """
        if model is blank, current model is used if exits, otherwise new model
        is created.
        """
        import modelx as mx

        if model:
            return mx.get_models()[model]
        else:
            return mx.cur_model() if mx.cur_model() else mx.new_model()

    def mx_get_object(self, msgtype, fullname=None, attrs=None):

        import modelx as mx
        if fullname is None:
            obj = mx.cur_model()
        else:
            obj = mx.get_object(fullname, as_proxy=True)

        if obj is not None:
            if attrs is None:
                data = obj._baseattrs
            else:
                data = obj._to_attrdict(attrs)
        else:
            data = None

        self.send_mx_msg(msgtype, data=data)

    def mx_get_modellist(self):
        """Returns a list of model info.

         Returns a list of dicts of basic model attributes.
         The first element of the list is the current model info.
         None if not current model is set.
         """

        import modelx as mx
        from modelx.core.base import Interface

        data = [Interface._baseattrs.fget(m) for m in mx.get_models().values()]

        if mx.cur_model():
            cur = Interface._baseattrs.fget(mx.cur_model())
        else:
            cur = None

        data.insert(0, cur)

        if spyder.version_info > (4,):
            return data
        else:
            self.send_mx_msg("modellist", data=data)

    def mx_get_codelist(self, fullname):
        import modelx as mx

        try:
            obj = mx.get_object(fullname)
            data = obj._to_attrdict(['formula'])
        except:
            data = None

        self.send_mx_msg('codelist', data=data)

    def mx_get_evalresult(self, msgtype, data):

        # The code below is based on SpyderKernel.get_value
        try:
            self.send_mx_msg(msgtype, data=data)
        except:
            # * There is no need to inform users about
            #   these errors.
            # * value = None makes Spyder to ignore
            #   petitions to display a value
            self.send_mx_msg(msgtype, data=None)

        self._do_publish_pdb_state = False

    def mx_get_adjacent(self, msgtype, obj: str,
                        jsonargs: str, adjacency: str):

        import modelx as mx
        from modelx.core.base import Interface

        args = json.loads(jsonargs, object_hook=hinted_tuple_hook)
        node = mx.get_object(obj).node(*args)
        nodes = getattr(node, adjacency)
        attrs = [node._baseattrs for node in nodes]

        for node in attrs:
            if isinstance(node["value"], Interface):
                node["value"] = repr(node["value"])

        if spyder.version_info > (4,):
            return attrs
        else:
            content = {'mx_obj': obj, 'mx_args': args, 'mx_adjacency': adjacency}
            self.send_mx_msg(msgtype, content=content, data=attrs)

    def send_mx_msg(self, mx_msgtype, content=None, data=None):
        """
        Publish custom messages to the Spyder frontend.

        This code is modified from send_spyder_msg in spyder-kernel v0.2.4

        Parameters
        ----------

        mx_msgtype: str
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
        content['mx_msgtype'] = mx_msgtype
        self.session.send(
            self.iopub_socket,
            'modelx_msg',
            content=content,
            buffers=[cloudpickle.dumps(data, protocol=2)],
            parent=self._parent_header)

