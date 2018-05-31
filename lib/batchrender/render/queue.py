# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging

from . import core
from .. import model
from .task import Task

LOGGER = logging.getLogger(__name__)


class Queue(core.RenderObject):
    """Task render quene.  """

    def __init__(self, data_model):
        from ..model import FilesProxyModel
        assert isinstance(data_model, FilesProxyModel), type(data_model)

        self.model = data_model
        super(Queue, self).__init__()
        self.tasks = list(self._all_tasks())

        self.model.layoutChanged.connect(self.update)

    def __contains__(self, item):
        if isinstance(item, (str, unicode)):
            return any(i for i in self if i.filename == item)
        return any(i for i in self if i == item)

    def __nonzero__(self):
        return any(self.enabled_tasks())

    def __len__(self):
        return len(self.enabled_tasks())

    def __str__(self):
        return 'render.Queue<{}>'.format(',\n'.join(self.model.checked_files()))

    def get(self):
        """Get first task from queue.  """

        try:
            return next(self.enabled_tasks())
        except StopIteration:
            self.finished.emit()
            raise

    def enabled_tasks(self):
        """Iterator for enabled tasks in queue.  """

        return self._task_iterator(self.model.checked_files())

    def _all_tasks(self):
        """Iterator for all tasks in queue.  """

        return self._task_iterator(self.model.all_files())

    def update_remains(self):
        """Caculate remains time.  """

        ret = 0
        for i in self.tasks:
            assert isinstance(i, Task)
            if i.state & model.DOING:
                ret += (i.remains
                        or i.estimate_time)
            else:
                ret += i.estimate_time
        self.remains = ret

    def _task_iterator(self, files):
        source_model = self.model.sourceModel()

        def _get_task(filename):
            try:
                return Task(filename, source_model)
            except IOError:
                return None
        return (j for j in (_get_task(i) for i in files) if isinstance(j, Task))

    def update(self):
        """Update the queue.  """

        self.tasks = list(self._all_tasks())
        self.update_remains()
