# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Fumito Hamamura
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Spyder modelx Plugin."""


from ._version import __version__

# The following statements are required to register this 3rd party plugin:

from .modelxplugin import ModelxPlugin

PLUGIN_CLASS = ModelxPlugin
