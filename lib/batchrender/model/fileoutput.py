# -*- coding=UTF-8 -*-
"""Output file model.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
from collections import namedtuple
from pathlib import PurePath

import sqlalchemy
from PySide2.QtCore import QAbstractListModel, Qt
from sqlalchemy import desc

from .. import database as db
from ..codectools import get_unicode as u
from ..framerange import FrameRange
from ..mixin import UnicodeTrMixin

Sequence = namedtuple('sequence', ('path', 'timestamp', 'range'))

LOGGER = logging.getLogger(__name__)


class FileOutputModel(UnicodeTrMixin, QAbstractListModel):
    """Model for output file data.  """

    def __init__(self, parent=None):
        super(FileOutputModel, self).__init__(parent)
        self._data = []

    def update(self):
        """Update item from database.  """
        with db.util.session_scope(db.core.Session(expire_on_commit=False)) as sess:
            outputs = sess.query(
                db.Output
            ).order_by(
                desc(db.Output.timestamp)
            ).limit(500).all()

        outputs_groups = db.output.group_by_pattern(outputs)
        data = []
        for k, v in list(outputs_groups.items()):
            if len(v) == 1:
                data.append(v[0])
            else:
                sequences = Sequence(PurePath(k), max(
                    i.timestamp for i in v), FrameRange(i.frame for i in v))
                data.append(sequences)

        data.sort(key=lambda x: x.timestamp, reverse=True)

        if self._data != data:
            self.beginResetModel()
            self._data = data
            self.endResetModel()
        LOGGER.debug('File output model updated')

    def rowCount(self, _):
        """(Override).  """

        return len(self._data)

    def data(self, index, role=Qt.DisplayRole):
        """(Override).  """

        row = index.row()
        # column = index.colomn()
        item = self._data[row]

        if role == Qt.DisplayRole:
            return item.path.name
        elif role == Qt.ToolTipRole:
            rows = [item.timestamp.diff_for_humans(), u(item.path.as_posix())]
            if isinstance(item, Sequence):
                rows.append(self.tr('Range: {}').format(item.range))
            return '\n'.join(rows)
        elif role == Qt.EditRole:
            return item
        return None

    def flags(self, _):
        """(Override).  """
        return Qt.ItemIsEnabled
