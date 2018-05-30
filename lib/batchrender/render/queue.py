# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import time

from . import core
from .. import model
from .task import Task
from .. import database
LOGGER = logging.getLogger(__name__)


class Queue(core.RenderObject):
    """Task render quene.  """

    def __init__(self, model):
        from ..model import FilesProxyModel
        assert isinstance(model, FilesProxyModel), type(model)
        super(Queue, self).__init__()
        self.model = model

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

    def get(self, session=database.SESSION):
        """Get first task from queue.  """

        try:
            return self.enabled_tasks(session).next()
        except StopIteration:
            time.sleep(1)
            return self.get()

    def enabled_tasks(self, session=database.SESSION):
        """Iterator for enabled tasks in queue.  """

        return self._task_iterator(self.model.checked_files(), session)

    def all_tasks(self, session=database.SESSION):
        """Iterator for all tasks in queue.  """

        return self._task_iterator(self.model.all_files(), session)

    @property
    def remains(self):
        ret = 0
        for i in self.all_tasks():
            assert isinstance(i, Task)
            if i.state & model.DOING:
                ret += (i.remains
                        or i.estimate_time)
            else:
                ret += i.estimate_time

        return ret

    def _task_iterator(self, files, session):
        def _get_task(filename):
            try:
                return Task(filename, queue=self, session=session)
            except IOError:
                return None
        return (j for j in (_get_task(i) for i in files) if isinstance(j, Task))
