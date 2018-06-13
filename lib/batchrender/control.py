# -*- coding=UTF-8 -*-
"""Batchrender control.  """
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from Qt.QtCore import QObject, Signal

from . import render
from .config import CONFIG
from . import model as qmodel
from . import filetools
LOGGER = logging.getLogger(__name__)


class Controller(QObject):
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

        # Initiate render object.
        self.queue = render.Queue(self.model)
        self.slave = render.Slave(self.queue)

        self.is_updating = False

        self.model.layoutChanged.connect(self.update_model)
        self.model.dataChanged.connect(self.update_model)
        self.slave.progressed.connect(self.queue.update_remains)

    def start(self):
        """Start rendering.  """
        self.slave.start()

    def stop(self):
        """Stop rendering.  """
        self.slave.stop()

    def change_root(self, path):
        """Change root directory.  """

        path = os.path.normpath(path)
        CONFIG['DIR'] = path
        self.model.sourceModel().setRootPath(path)
        self.root_changed.emit(path)

    def update_model(self):
        """Update directory model.  """

        if self.is_updating:
            return

        self.is_updating = True
        try:
            self._update_model()
        finally:
            self.is_updating = False

    def enable_all(self):
        for i in self.queue.all_tasks():
            i.state &= ~qmodel.DISABLED

    def invert_disable_state(self):
        for i in self.queue.all_tasks():
            if i.state & qmodel.DISABLED:
                i.state &= ~qmodel.DISABLED
            else:
                i.state |= qmodel.DISABLED

    def remove(self, indexes):
        """Archive related file.  """

        for i in self.queue.task_iterator(indexes):
            if i.is_file_exists():
                i.file.archive()

    def _update_model(self):
        self.model.sort(0)
