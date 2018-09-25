# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

import six
from Qt.QtCore import QObject, Qt

from . import core
from .. import database
from ..codectools import get_encoded as e
from .directory import DirectoryModel

LOGGER = logging.getLogger(__name__)


def _map_model_data(role, docstring=None):
    def _get_model_data(self):
        return self.model.data(self.index, role)

    def _set_model_data(self, value):
        self.model.setData(self.index, value, role)

    return property(_get_model_data, _set_model_data, doc=docstring)


@six.python_2_unicode_compatible
class Task(QObject):
    """Task data.  """

    state = _map_model_data(core.ROLE_STATE, 'Task state.')
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
    file = _map_model_data(core.ROLE_FILE, 'Database file object.')

    def __init__(self, index, dir_model):
        assert isinstance(dir_model, DirectoryModel), type(dir_model)

        self.model = dir_model
        self.index = index

        self._tempfile = None
        self.proc = None
        self.start_time = None
        super(Task, self).__init__()
        self.remains_changed.connect(self.on_changed)

    def __eq__(self, other):
        if isinstance(other, Task):
            other = other.path
        return self.path == other

    def __str__(self):
        return '<Task: priority={0.priority}, label={0.label}, state={0.state:b}>'.format(self)

    @property
    def estimate(self):
        """Estimate time to render.  """

        ret = self._estimate
        if not ret:
            with database.util.session_scope() as sess:
                ret = self._update_estimate(sess)
        return ret

    def is_file_exists(self):
        """Check if the task file exists.  """

        return os.path.exists(e(self.path))

    def _update_file(self, session, is_recreate=True):
        """Update the related file record.  """

        record = (database.File.from_path(self.path)
                  if is_recreate or not self.file else self.file)
        record = session.merge(record)
        session.refresh(record)
        self.file = record
        self._update_range()

    def _update_range(self):
        if not self.range:
            self.range = self.file.range()
        if self.file.has_sequence():
            remains = self.range - self.file.rendered_frames()
            self.range = remains or self.range

    def _update_estimate(self, session):
        self._update_file(session, is_recreate=False)
        ret = self.file.estimate_cost(self.frames)
        old = self._estimate
        self._estimate = ret
        if old != ret:
            self.changed.emit()
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
        self._update_range()
