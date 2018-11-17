
import sys

# Third party imports
from qtpy.QtCore import Signal, Slot
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (QLabel, QVBoxLayout, QWidget,
                            QMainWindow, QScrollArea)
from spyder.widgets.sourcecode.codeeditor import CodeEditor


sampletexts = [
'''\
def SizeExpsAcq(t):
    """Acquisition expense per policy at time t"""
    if t == 0:
        return (SizeAnnPrem(t) * asmp.ExpsAcqAnnPrem
                + (SizeSumAssured(t) * asmp.ExpsAcqSA + asmp.ExpsAcqPol)
                * scen.InflFactor(t) / scen.InflFactor(0))
    else:
        return 0
    print('foo')
    print('foo')
    print('foo')
    print('foo')
    print('foo')
    print('foo')        
''',

'''\
def SizeExpsMaint(t):
    """Maintenance expense per policy at time t"""
    return (SizeAnnPrem(t) * asmp.ExpsMaintAnnPrem
            + (SizeSumAssured(t) * asmp.ExpsMaintSA + asmp.ExpsMaintPol)
            * scen.InflFactor(t))
''',

'''\
def SizeExpsOther(t):
    """Other expenses per policy at time t"""
    return 0''']

code2insert = '''\
def InflFactor(t):
    if t == 0:
        return 1
    else:
        return InflFactor(t-1) / (1 + asmp.InflRate)
'''

# ===============================================================================
# Editor + Class browser test
# ===============================================================================

class CodePane(QWidget):

    def __init__(self, parent, title='', code=''):
        QWidget.__init__(self, parent)

        self.editor = editor = CodeEditor(self)
        editor.setup_editor(linenumbers=False, language='Python',
                            markers=True, tab_mode=False,
                            font=QFont("Courier New", 10),
                            show_blanks=True, color_scheme='Zenburn',
                            scrollflagarea=False)

        editor.fontMetrics().lineSpacing()
        editor.setReadOnly(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        layout.addWidget(editor)  # , stretch=1)
        self.setLayout(layout)

        self.setCode(code)

    def setCode(self, code):
        self.editor.set_text(code)
        self.editor.setFixedHeight(
            self.getEditorHeight(self.editor.blockCount() + 2))

    def getEditorHeight(self, nRows):

        pdoc = self.editor.document()
        fm = self.editor.fontMetrics()
        margins = self.editor.contentsMargins()

        nHeight = fm.lineSpacing() * nRows\
                  + (pdoc.documentMargin() + self.editor.frameWidth()) * 2 \
                  + margins.top() + margins.bottom()

        return nHeight


class CodeListWidget(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def insertCode(self, index, title='', code=''):
        codepane = CodePane(self, title, code)

        if index < self.layout.count():
            self.layout.insertWidget(index, codepane)
        else:
            self.layout.addWidget(codepane)

    def removeCode(self, index):
        item = self.layout.takeAt(index)
        item.widget().deleteLater()

    def appendCode(self, title='', code=''):
        codepane = CodePane(self, title, code)
        self.layout.addWidget(codepane)


def test(fname):
    from spyder.utils.qthelpers import qapplication
    app = qapplication(test_time=5)
    win = QMainWindow(None)
    scrollarea = QScrollArea(win)
    win.setCentralWidget(scrollarea)
    scrollarea.setWidgetResizable(True)

    tw = CodeListWidget(None)
    scrollarea.setWidget(tw)
    # win = CodeListWidget(None)

    win.show()

    for text in sampletexts:
        tw.appendCode('Cells Foo', text)

    tw.insertCode(2, 'InflFactor', code2insert)
    tw.removeCode(3)


    sys.exit(app.exec_())


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fname = sys.argv[1]
    else:
        fname = __file__
    test(fname)
