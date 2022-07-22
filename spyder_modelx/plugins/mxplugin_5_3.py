from .mxplugin_5_base import (
    MxPluginMainWidgetBase,
    ModelxPlugin as _ModelxPlugin
)
from .mxconsole_5_3 import MxConsoleAPI_5_3


class MxPluginMainWidget_5_3(MxConsoleAPI_5_3, MxPluginMainWidgetBase):
    pass


class ModelxPlugin_5_3(_ModelxPlugin):
    WIDGET_CLASS = MxPluginMainWidget_5_3