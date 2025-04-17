import spyder

if spyder.version_info > (6,):
    from .mxcodeeditor_6 import MxCodeEditor, BaseCodePane, _
else:
    from .mxcodeeditor_5 import MxCodeEditor, BaseCodePane, _
