# Copyright (c) 2017-2019 Fumito Hamamura <fumito.ham@gmail.com>

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

import sys
import modelx as mx

__all__ = ["get_modeltree", "get_tree"]

from qtpy.QtCore import Slot, Signal
from qtpy.QtWidgets import (
    QApplication, QTreeView, QWidget, QVBoxLayout, QComboBox, QPushButton)
from modelx.qtgui.modeltree import ModelTreeModel



def get_modeltree(model=None):
    """Alias to :func:`get_tree`."""
    if model is None:
        model = mx.cur_model()
    treemodel = ModelTreeModel(model._baseattrs)
    view = QTreeView()
    view.setModel(treemodel)
    view.setWindowTitle("Model %s" % model.name)
    view.setAlternatingRowColors(True)
    return view


def get_tree(model=None):
    """Get QTreeView object containing the model tree.

    Args:
        model: :class:`Model <modelx.core.model.Model>` object.
            Defaults to the current model.
    """
    if model is None:
        model = mx.cur_model()
    treemodel = ModelTreeModel(model._baseattrs)
    view = QTreeView()
    view.setModel(treemodel)
    view.setWindowTitle("Model %s" % model.name)
    view.setAlternatingRowColors(True)
    return view


class Window(QWidget):
    def __init__(self, model):
        super(Window, self).__init__()

        self.sourceView = get_modeltree(model)
        self.combo = MxModelSelector(self)
        self.button = QPushButton(text="Add")
        self.button.clicked.connect(self.add_model)
        self.delbutton = QPushButton(text="Del")
        self.delbutton.clicked.connect(self.del_model)
        self.curbutton = QPushButton(text="Cur")
        self.curbutton.clicked.connect(self.set_current)

        mainLayout = QVBoxLayout()


        mainLayout.addWidget(self.combo)
        mainLayout.addWidget(self.sourceView)
        mainLayout.addWidget(self.button)
        mainLayout.addWidget(self.delbutton)
        mainLayout.addWidget(self.curbutton)
        self.setLayout(mainLayout)

        self.setWindowTitle("Basic Sort/Filter Model")
        self.resize(500, 450)


    def add_model(self):
        mx.new_model()
        self.combo.update_modellist(get_modellist())

    def del_model(self):
        m = mx.cur_model()
        if m:
            m.close()
        self.combo.update_modellist(get_modellist())

    def set_current(self):
        idx = self.combo.currentIndex()

        if idx > 0:
            mx.cur_model(self.combo.modellist[idx]["name"])

        self.combo.update_modellist(get_modellist())


class MxModelSelector(QComboBox):

    sig_mxmodelselected = Signal()

    def __init__(self, parent):
        QComboBox.__init__(self, parent=parent)

        # modellist is a list of dicts that contains basic model attributes.
        # The first element represents the current model,
        # and it can be None if no current model is set.
        self.modellist = []

        self.activated.connect(self.on_activated)
        self.currentIndexChanged.connect(self.on_currentIndexChanged)
        self.editTextChanged.connect(self.on_editTextChanged)
        self.highlighted.connect(self.on_highlighted)
        # self.textActivated.connect(self.on_textActivated)
        # self.textHighlighted.connect(self.on_textHighlighted)

    def get_selected_model(self, modellist=None):
        """Gets the name of the selected model."""

        if modellist:
            self.update_modellist(modellist)

        idx = self.currentIndex()
        if idx < 0:
            return ""
        elif idx == 0 and not self.modellist[idx]:
            return ""
        else:
            m = self.modellist[idx]
            return m["name"]

    def update_modellist(self, modellist):
        """Update the list of models.

        modellist can be [None, ...]

        if the current model is previously selected, select the current model
        after updating.
        if the previously selected model does not exist after updating,
        the current model is selected.
        """

        if not self.is_modellist_updated(modellist):
            return

        idx = self.currentIndex()

        if idx > 0:
            modelid = self.modellist[idx]["id"]

        textlist = []
        newidx = 0
        for i, m in enumerate(modellist):
            if not i:   # Current model
                modelname = m["name"] if m else "None"
                textlist.append("Current Model - %s" % modelname)
            else:
                if idx > 0 and m["id"] == modelid:
                    newidx = i
                textlist.append(m["name"])

        self.clear()
        self.addItems(textlist)

        if idx > 0:
            self.setCurrentIndex(newidx)

        self.modellist = modellist


    def is_modellist_updated(self, modellist):

        if len(self.modellist) != len(modellist):
            return True

        for cur, oth in zip(self.modellist, modellist):
            if cur is None:
                if oth is None:
                    continue
                else:
                    return True
            if cur["name"] == oth["name"] and cur["id"] == oth["id"]:
                continue
            else:
                return True

        return False

    def on_activated(self, i):
        print("on_activated: %s" % repr(i))

    @Slot(int)
    @Slot(str)
    def on_currentIndexChanged(self, v):
        print("on_currentIndexChanged: %s" % v)

    def on_editTextChanged(self, s):
        print("on_editTextChanged: %s" % s)

    def on_highlighted(self, i):
        print("on_highlighted: %s" % i)

    def on_textActivated(self, s):
        print("on_textActivated: %s" % s)

    def on_textHighlighted(self, s):
        print("on_textHighlighted: %s" % s)


def get_modellist():

    modellist = [m._baseattrs for m in mx.get_models().values()]
    cur = mx.cur_model()
    if cur:
        modellist.insert(0, mx.cur_model()._baseattrs)
    else:
        modellist.insert(0, None)
    return modellist


if __name__ == "__main__":

    model, space = mx.new_model("ModelA"), mx.new_space("SpaceA")
    model, space = mx.new_model("ModelB"), mx.new_space("SpaceB")
    model, space = mx.new_model("ModelC"), mx.new_space("SpaceC")

    @mx.defcells
    def fibo(x):
        if x == 0 or x == 1:
            return x
        else:
            return fibo[x - 1] + fibo[x - 2]

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    w = Window(model)
    mx.get_models()["ModelA"].close()
    w.show()
    w.combo.update_modellist(get_modellist())
    app.exec_()

