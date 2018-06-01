# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from Qt.QtCore import QObject, Qt

from . import core
from .. import database
from .directory import DirectoryModel

LOGGER = logging.getLogger(__name__)


def _map_model_data(role, docstring=None):
    def _get_model_data(self):
        return self.model.data(self.index, role)

    def _set_model_data(self, value):
        self.model.setData(self.index, value, role)

    return property(_get_model_data, _set_model_data, doc=docstring)


class Task(QObject):
    """Task data.  """

    state = _map_model_data(core.ROLE_STATUS, 'Task state.')
    range = _map_model_data(core.ROLE_RANGE, 'Render range.')
    priority = _map_model_data(core.ROLE_PRIORITY, 'Render range.')
    remains = _map_model_data(core.ROLE_REMAINS, 'Remains time to render.')
    frames = _map_model_data(core.ROLE_FRAMES, 'Task frame count.')
    error_count = _map_model_data(
        core.ROLE_ERROR_COUNT, 'Error count during rendering.')
    path = _map_model_data(DirectoryModel.FilePathRole, 'File path.')
    label = _map_model_data(Qt.DisplayRole, 'Task label.')

    _estimate = _map_model_data(
        core.ROLE_ESTIMATE, 'Estimate time to render.')
    _file = _map_model_data(core.ROLE_FILE, 'Database file object.')

    def __init__(self, index, dir_model):
        assert isinstance(dir_model, DirectoryModel), type(dir_model)

        self._tempfile = None
        self.proc = None
        self.start_time = None

        self.model = dir_model
        self.index = index

        super(Task, self).__init__()

    def __eq__(self, other):
        if isinstance(other, Task):
            other = other.path
        return self.path == other

    def __str__(self):
        return '<{0.priority}: {0.label}: {0.state:b}>'.format(self)

    def __unicode__(self):
        return '<任务 {0.label}: 优先级 {0.priority}, 状态 {0.state:b}>'.format(self)

    @property
    def file(self):
        """Database file object.  """

        ret = self._file
        if not ret:
            ret = self._update_file()
        return ret

    @property
    def estimate(self):
        """Estimate time to render.  """

        ret = self._estimate
        if not ret:
            ret = self._update_estimate()
        return ret

    def is_file_exists(self):
        """Check if the task file exists.  """

        try:
            self._update_file()
            return True
        except IOError:
            return False

    def _update_file(self):
        ret = database.File.from_path(self.path, database.SESSION)
        self._file = ret
        if not self.range:
            self.range = self.file.range_text()
        return ret

    def _update_estimate(self):
        ret = self.file.estimate_cost(self.frames)
        self._estimate = ret
        return ret

    def _set_state(self, state, value):
        if value:
            self.state |= state
        else:
            self.state &= ~state

    def _update_file_range(self, first_frame, last_frame):
        old_fisrt, old_last = self.file.first_frame, self.file.last_frame
        if old_fisrt is not None:
            first_frame = min(first_frame, old_fisrt)
        if old_last is not None:
            last_frame = max(last_frame, old_last)

        self.file.first_frame = first_frame
        self.file.last_frame = last_frame
