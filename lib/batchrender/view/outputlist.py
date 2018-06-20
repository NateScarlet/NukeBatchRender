# -*- coding=UTF-8 -*-
"""List view widget for output files.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from Qt import QtGui
from Qt.QtCore import Qt
from Qt.QtWidgets import QAction, QFileDialog, QListView, QMenu

from ..codectools import get_unicode as u
from ..mixin import UnicodeTrMixin
from ..model.fileoutput import Sequence


class OutputListView(UnicodeTrMixin, QListView):
    """View on output files.  """

    def __init__(self, parent, control):
        super(OutputListView, self).__init__(parent)
        from ..control import Controller
        assert isinstance(control, Controller), type(control)
        self.control = control

    def contextMenuEvent(self, event):
        item = self.model().data(self.indexAt(event.pos()), Qt.EditRole)
        if isinstance(item, Sequence):
            menu = QMenu(self)
            action = QAction(self.tr('Convert to mov...'), self)
            action.triggered.connect(lambda: self.convert_to_mov(item))
            menu.addAction(action)
            action = QAction(self.tr('Convert to mov in situ'), self)
            action.triggered.connect(lambda: self.convert_to_mov_in_situ(item))
            menu.addAction(action)
            menu.popup(QtGui.QCursor.pos())

    def convert_to_mov(self, item):
        """Convert sequence to mov.  """

        assert isinstance(item, Sequence), type(item)
        dst, _ = QFileDialog.getSaveFileName(
            self, self.tr('Choose mov save path'),
            u(item.path.parent), '*.mov'
        )
        if not dst:
            return

        self.control.sequence_to_mov(item, dst)

    def convert_to_mov_in_situ(self, item):
        """Convert sequence to mov in situ.  """

        def _without_suffix(path):
            ret = path.with_suffix('')
            if ret.suffix:
                return _without_suffix(ret)
            return ret
        dst = u(_without_suffix(item.path).with_suffix('.mov'))

        self.control.sequence_to_mov(item, dst)
