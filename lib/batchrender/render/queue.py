# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import os

import time

from ..files import FILES
from . import core
from .task import Task

LOGGER = logging.getLogger(__name__)


class Queue(core.RenderObject):
    """Task render quene.  """

    def __init__(self):
        super(Queue, self).__init__()
        self._list = []
        self.changed.connect(self.sort)

    def __contains__(self, item):
        if isinstance(item, (str, unicode)):
            return any(i for i in self if i.filename == item)
        return any(i for i in self if i == item)

    def __nonzero__(self):
        return any(self.enabled_tasks())

    def __len__(self):
        return self._list.__len__()

    def __str__(self):
        return '[{}]'.format(',\n'.join(str(i) for i in self._list))

    def __getitem__(self, name):
        if isinstance(name, int):
            return self._list.__getitem__(name)
        elif isinstance(name, (str, unicode)):
            try:
                return [i for i in self if i.filename == name][0]
            except IndexError:
                raise ValueError('No task match filename: %s' % name)
        elif isinstance(name, Task):
            return self.__getitem__(name.filename)
        else:
            raise TypeError('Accept int or str, got %s' % type(name))

    def sort(self):
        """Sort queue.  """

        self._list.sort(key=lambda x: (not x.state & core.DOING,
                                       x.state, -x.priority, x.mtime))

    def get(self):
        """Get first task from queue.  """

        try:
            return self.enabled_tasks().next()
        except StopIteration:
            time.sleep(1)
            return self.get()

    def put(self, item):
        """Put task to queue.  """

        if item in tuple(self):
            self[item].update()
            return
        elif not isinstance(item, Task):
            item = Task(item)
        item.queue.add(self)
        self._list.append(item)
        self.changed.emit()
        LOGGER.debug('Add task: %s', item)

    def remove(self, item):
        """Archive file, then remove task and file.  """

        item = self[item]
        assert isinstance(item, Task)
        if item.state & core.DOING:
            LOGGER.error('不能移除正在进行的任务: %s', item.filename)
            return
        filename = item.filename
        LOGGER.debug('Remove task: %s', item)

        if os.path.exists(filename):
            FILES.remove(filename)
        self._list.remove(item)
        item.queue.discard(self)
        self.changed.emit()

    def enabled_tasks(self):
        """All enabled task in queue. """

        if not self._list:
            return ()
        self.sort()
        return (i for i in tuple(self) if not i.state)

    @property
    def remains(self):
        ret = 0
        for i in (i for i in tuple(self) if not i.state or i.state & core.DOING):
            assert isinstance(i, Task)
            if i.state & core.DOING:
                ret += (i.remains
                        or i.estimate_time)
            else:
                ret += i.estimate_time

        return ret

    def on_changed(self):
        self.sort()
