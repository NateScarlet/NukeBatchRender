# -*- coding=UTF-8 -*-
"""Batchrender control.  """
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from Qt.QtCore import QObject, Signal, Qt

from . import render
from .config import CONFIG
from .model import DirectoryModel, FilesProxyModel, ROLE_PRIORITY, ROLE_RANGE, ROLE_STATUS

LOGGER = logging.getLogger(__name__)


class Controller(QObject):
    """Batchrender controller.  """
    root_changed = Signal(str)

    def __init__(self, parent=None):
        super(Controller, self).__init__(parent)
        model = DirectoryModel(self)
        proxy_model = FilesProxyModel(self)
        proxy_model.setSourceModel(model)
        self.model = proxy_model

        # Initiate render object.
        self.queue = render.Queue(self.model)
        self.slave = render.Slave()

        self.is_updating = False

        self.model.layoutChanged.connect(self.update_model)
        self.model.dataChanged.connect(self.update_model)

    def start(self):
        """Start rendering.  """
        self.slave.start(self.queue)

    def stop(self):
        """Stop rendering.  """
        self.slave.stop()

    def change_root(self, path):
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

    def _update_model(self):
        model = self.model
        row_count = model.rowCount()
        root_index = model.root_index()
        for i in range(row_count):
            index = self.model.index(i, 0, root_index)
            _set_model_default(model, index)
        self.model.sort(0)

    def create_task(self, file):
        pass


def _set_model_default(model, index):
    if model.data(index, ROLE_PRIORITY) is None:
        model.setData(index, 0, ROLE_PRIORITY)
