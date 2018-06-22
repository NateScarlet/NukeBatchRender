# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from . import core
from .. import model
from .task import NukeTask

LOGGER = logging.getLogger(__name__)


class Queue(core.RenderObject):
    """Task render quene.  """

    def __init__(self, data_model):
        from ..model import FilesProxyModel
        assert isinstance(data_model, FilesProxyModel), type(data_model)

        self.model = data_model
        self._task_cache = {}
        super(Queue, self).__init__()

        self.model.layoutChanged.connect(self.changed)
        self.model.rowsRemoved.connect(self.changed)

    def __bool__(self):
        return any(self.enabled_tasks())
    __nonzero__ = __bool__

    def get(self):
        """Get first task from queue.  """

        try:
            return next(i for i in self.enabled_tasks()
                        if i.is_file_exists())
        except StopIteration:
            self.finished.emit()
            raise

    def enabled_tasks(self):
        """Iterator for enabled tasks in queue.  """

        return self.task_iterator(i for i in self.model.iter_checked())

    def selected_tasks(self):
        """Iterator for user selected tasks in queue.  """

        indexes = self.model.selectedIndexes()
        return self.task_iterator(indexes)

    def all_tasks(self):
        """Iterator for all tasks in queue.  """

        indexes = self.model.iter()
        return self.task_iterator(indexes)

    def task_iterator(self, indexes):
        """Generator for tasks from indexes.

        Args:
            indexes (list[QModelIndex]): Indexes in this model.

        Returns:
            Generator: Tasks.
        """

        return (self._get_task(i) for i in indexes)

    def _get_task(self, index):
        if index not in self._task_cache:
            source_model = self.model.sourceModel()
            self._task_cache[index] = NukeTask(
                self.model.mapToSource(index), source_model)
        return self._task_cache[index]

    def update_remains(self):
        """Caculate remains time.  """

        ret = 0
        for i in self.enabled_tasks():
            assert isinstance(i, model.Task)
            if i.state & model.DOING and i.remains is not None:
                ret += i.remains
            else:
                ret += i.estimate
        self.remains = ret

    def on_changed(self):
        self.update_remains()
