# -*- coding=UTF-8 -*-
"""Task rendering.  """

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
        super(Queue, self).__init__()

        self.model.layoutChanged.connect(self.changed)
        self.model.rowsRemoved.connect(self.changed)

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

        return self._task_iterator(i for i in self.model.iter_checked())

    def update_remains(self):
        """Caculate remains time.  """

        ret = 0
        for i in self.enabled_tasks():
            assert isinstance(i, model.Task)
            if i.state & model.FINISHED:
                pass
            elif i.state & model.DOING and i.remains is not None:
                ret += i.remains
            else:
                ret += i.estimate
        self.remains = ret

    def on_changed(self):
        self.update_remains()

    def _task_iterator(self, indexes):
        source_model = self.model.sourceModel()
        return (NukeTask(self.model.mapToSource(i), source_model) for i in indexes)
