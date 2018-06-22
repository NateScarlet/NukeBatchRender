# -*- coding=UTF-8 -*-
"""Batchrender control.  """
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from Qt.QtCore import QObject, Signal
from Qt.QtWidgets import QMessageBox

from . import actions, filetools
from . import model as qmodel
from . import render
from .codectools import get_unicode as u
from .config import CONFIG
from .mixin import UnicodeTrMixin
from .model.fileoutput import Sequence

LOGGER = logging.getLogger(__name__)


class Controller(UnicodeTrMixin, QObject):
    """Batchrender controller.  """

    root_changed = Signal(str)

    @classmethod
    def create_task(cls, filepath):
        """Create a task from file.  """

        filetools.copy(filepath, CONFIG['DIR'])

    def __init__(self, parent=None):
        super(Controller, self).__init__(parent)
        model = qmodel.DirectoryModel(self)
        proxy_model = qmodel.FilesProxyModel(self)
        proxy_model.setSourceModel(model)
        self.model = proxy_model
        self.output_model = qmodel.FileOutputModel(self)
        self.output_model.update()

        # Initiate render object.
        self.queue = render.Queue(self.model)
        self.slave = render.Slave(self.queue)

        self.slave.progressed.connect(self.queue.update_remains)
        self.slave.progressed.connect(self.output_model.update)

    def start(self):
        """Start rendering.  """
        self.slave.start()

    def abort(self):
        """Abort rendering.  """
        self.slave.abort()

    def change_root(self, path):
        """Change root directory.  """

        path = os.path.normpath(path)
        CONFIG['DIR'] = path
        self.model.sourceModel().setRootPath(path)
        self.root_changed.emit(path)

    def enable_all(self):
        """Enable all tasks.  """

        for i in list(self.queue.all_tasks()):
            i.state &= ~qmodel.DISABLED

    def invert_disable_state(self):
        """Invert disable state on all tasks.  """

        for i in list(self.queue.all_tasks()):
            if i.state & qmodel.DISABLED:
                i.state &= ~qmodel.DISABLED
            else:
                i.state |= qmodel.DISABLED

    def remove(self, indexes):
        """Archive related file.  """

        for i in self.queue.task_iterator(indexes):
            if i.is_file_exists():
                i.file.archive()

    def sequence_to_mov(self, sequence, dst):
        """Execute sequece convert.  """

        assert isinstance(sequence, Sequence), type(sequence)
        try:
            src = u(sequence.path)
            start_number = min(sequence.range)
            actions.convert_to_mov(src, dst, start_number)
        except RuntimeError:
            QMessageBox.critical(None, self.tr('Can not convert.'), self.tr(
                'This feature need FFMPEG installed.'))
