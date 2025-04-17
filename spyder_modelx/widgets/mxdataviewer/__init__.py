import spyder


if spyder.version_info > (6,):
    from .compat60 import (
        MxDataFrameViewer,
        MxArrayViewer,
        MxCollectionsViewer
    )
elif spyder.version_info > (5, 1):
    from .compat51 import (
        MxDataFrameViewer,
        MxArrayViewer,
        MxCollectionsViewer
    )
elif spyder.version_info > (5,):
    from .compat50 import (
        MxDataFrameViewer,
        MxArrayViewer,
        MxCollectionsViewer
    )
elif spyder.version_info > (4,):
    from .compat401 import (
        MxDataFrameViewer,
        MxArrayViewer,
        MxCollectionsViewer
    )
else:
    from .compat32 import (
        MxDataFrameViewer,
        MxArrayViewer
    )
    if spyder.version_info > (3, 3):
        from .compat33 import MxCollectionsViewer
    else:
        from .compat32 import MxCollectionsViewer