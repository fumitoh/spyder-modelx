# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Fumito Hamamura
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""modelx Widget."""

from qtpy.QtWidgets import QWidget

class ModelxWidget(QWidget):
    """modelx widget."""
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.setWindowTitle("modelx")
