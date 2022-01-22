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

# Standard library imports
import ast

# Third party imports
from qtpy.QtWidgets import QLineEdit


class MxPyExprLineEdit(QLineEdit):
    """A text form to enter a Python expression for MxDataFrameViewer."""

    def __init__(self, parent, font):
        super().__init__(parent)
        self.setFont(font)

    def is_empty(self):
        """Check if the text is empty."""
        return not bool(self.text())

    def is_valid_expr(self):
        """Check if the text is a valid Python expression."""
        try:
            ast.parse(self.text(), mode='eval')
        except SyntaxError:
            return False

        return True

    def get_expr(self):
        """Return the entered expression, or None if invalid."""
        if self.is_empty():
            return ''
        elif self.is_valid_expr():
            return self.text()
        else:
            return None

