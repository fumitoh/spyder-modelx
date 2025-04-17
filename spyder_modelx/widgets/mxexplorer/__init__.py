import spyder

if spyder.version_info > (6,):
    from .mxexplorer_6 import MxMainWidget
else:
    from .mxexplorer_5 import MxMainWidget
