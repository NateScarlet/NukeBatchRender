# -*- coding=UTF-8 -*-
"""Output file model.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from Qt.QtCore import QAbstractListModel, Qt

from .. import database


class OutputFileModel(QAbstractListModel):
    """Model for output file data.  """

    def __init__(self, parent=None):
        super(OutputFileModel, self).__init__(parent)
        self._data = []

    def update(self):
        """Update item from database.  """

        data = database.SESSION.query(database.Output).all()
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
        assert isinstance(item, database.Output)

        if role == Qt.DisplayRole:
            return item.path.as_posix()

        return None

    def flags(self, _):
        """(Override).  """
        return Qt.ItemIsEnabled
