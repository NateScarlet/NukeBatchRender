# -*- coding=UTF-8 -*-
"""Output file model.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import pendulum
from Qt.QtCore import QAbstractListModel, Qt
from sqlalchemy import desc

from .. import database as db


class FileOutputModel(QAbstractListModel):
    """Model for output file data.  """

    def __init__(self, parent=None):
        super(FileOutputModel, self).__init__(parent)
        self._data = []

    def update(self):
        """Update item from database.  """

        data = db.SESSION.query(db.Output).order_by(
            desc(db.Output.timestamp)).all()
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
        assert isinstance(item, db.Output)

        if role == Qt.DisplayRole:
            return '[{}]{}'.format(item.timestamp.diff_for_humans(locale='zh'), item.path.as_posix())

        return None

    def flags(self, _):
        """(Override).  """
        return Qt.ItemIsEnabled
