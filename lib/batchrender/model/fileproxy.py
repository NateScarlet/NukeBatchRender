# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from PySide2 import QtCore
from PySide2.QtCore import QSortFilterProxyModel, Qt
from six.moves import range

from .. import filetools
from ..mixin import UnicodeTrMixin
from . import core
from .directory import DirectoryModel

LOGGER = logging.getLogger(__name__)


class FilesProxyModel(UnicodeTrMixin, QSortFilterProxyModel):
    """Filter data by version.  """

    def __init__(self, parent):
        super(FilesProxyModel, self).__init__(parent)

        self.layoutChanged.connect(self._sort)
        self.dataChanged.connect(self._sort)
        self.is_updating = False

    def _sort(self):
        if self.is_updating:
            return
        self.is_updating = True
        self.sort(0)
        self.is_updating = False

    def filterAcceptsRow(self, source_row, source_parent):
        """Override.  """
        # pylint: disable=invalid-name

        model = self.sourceModel()
        assert isinstance(model, DirectoryModel)
        index = model.index(source_row, 0, source_parent)
        if model.isDir(index):
            return True
        data = model.data(index, model.FileNameRole)
        return data.endswith('.nk')

    def lessThan(self, left, right):
        """Override.  """

        model = self.sourceModel()
        return _get_sort_key(model, left) < _get_sort_key(model, right)

    def headerData(self, section, orientation, role):
        """Override.  """

        try:
            if orientation == Qt.Vertical:
                return {Qt.DisplayRole: section,
                        Qt.TextAlignmentRole: Qt.AlignLeft,
                        Qt.DecorationRole: None}[role]

            return [{Qt.DisplayRole: self.tr('File'), },
                    {Qt.DisplayRole: self.tr('Range'), },
                    {Qt.DisplayRole: self.tr('Priority'), }, ][section][role]
        except (KeyError, IndexError):
            return super(FilesProxyModel, self).headerData(
                section, orientation, role)

    def is_dir(self, index):
        """Wrapper for `self.sourceModel().isDir`.  """

        source_index = self.mapToSource(index)
        source_model = self.sourceModel()
        return source_model.isDir(source_index)

    def file_path(self, index):
        """Wrapper for `self.sourceModel().filePath`.  """

        index = self.mapToSource(index)
        return self.sourceModel().filePath(index)

    def iter(self):
        """Return all indexes under root.

        Returns:
            Generator: Model indexes.
        """

        root_index = self.root_index()
        count = self.rowCount(root_index)
        return (QtCore.QPersistentModelIndex(self.index(i, 0, root_index)) for i in range(count))

    def iter_checked(self):
        """Get indexes that row has been user checked.

        Returns:
            Generator: Model indexes.
        """

        return (i for i in self.iter()
                if self.data(i, Qt.CheckStateRole))

    def source_index(self, path):
        """Get source model index from path.

        Args:
            path (str): Path data.

        Returns:
            Qt.QtCore.ModelIndex: Index in source model.
        """

        source_model = self.sourceModel()
        return self.mapFromSource(source_model.index(path))

    def root_index(self):
        """Index of root path.  """

        model = self.sourceModel()
        return self.mapFromSource(model.index(model.rootPath()))

    def absolute_path(self, *path):
        """Convert path to absolute path.  """
        model = self.sourceModel()
        return os.path.abspath(os.path.join(model.rootPath(), *path))

    def old_version_files(self):
        """Files that has a lower version number.  """

        files = list(self.file_path(i) for i in self.iter())
        return (i for i in files if i not in filetools.version_filter(files))


def _get_sort_key(model, index):
    state = model.data(index, core.ROLE_STATE)
    return (state & core.DISABLED,
            -model.data(index, core.ROLE_PRIORITY),
            not state & core.FINISHED,
            model.lastModified(index).toPython())
