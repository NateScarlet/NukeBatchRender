# -*- coding=UTF-8 -*-
"""Output file model.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from collections import namedtuple

from pathlib2 import PurePath
from Qt.QtCore import QAbstractListModel, Qt
from sqlalchemy import desc

from .. import database as db
from ..framerange import FrameRange
from ..codectools import get_unicode as u

Sequence = namedtuple('sequence', ('path', 'timestamp', 'range'))


class FileOutputModel(QAbstractListModel):
    """Model for output file data.  """

    def __init__(self, parent=None):
        super(FileOutputModel, self).__init__(parent)
        self._data = []

    def update(self):
        """Update item from database.  """

        outputs = db.SESSION.query(db.Output).order_by(
            desc(db.Output.timestamp)).all()
        outputs_groups = db.output.group_by_pattern(outputs)
        data = []
        for k, v in outputs_groups.items():
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
                rows.append('范围: {}'.format(item.range))
            return '\n'.join(rows)
        elif role == Qt.EditRole:
            return item
        return None

    def flags(self, _):
        """(Override).  """
        return Qt.ItemIsEnabled
