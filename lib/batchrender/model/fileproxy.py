# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from Qt.QtCore import QSortFilterProxyModel, Qt
from six.moves import range

from . import core
from .. import filetools
from .directory import DirectoryModel

LOGGER = logging.getLogger(__name__)


class FilesProxyModel(QSortFilterProxyModel):
    """Filter data by version.  """

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
        left_data = _get_sort_data(model, left)
        right_data = _get_sort_data(model, right)
        return left_data < right_data

    def headerData(self, section, orientation, role):
        """Override.  """

        try:
            if orientation == Qt.Vertical:
                return {Qt.DisplayRole: section,
                        Qt.TextAlignmentRole: Qt.AlignLeft,
                        Qt.DecorationRole: None}[role]

            return [{Qt.DisplayRole: '文件', },
                    {Qt.DisplayRole: '范围', },
                    {Qt.DisplayRole: '优先级', }, ][section][role]
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
        return (self.index(i, 0, root_index) for i in range(count))

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


def _get_sort_data(model, index):
    return (model.data(index, Qt.CheckStateRole),
            model.data(index, core.ROLE_STATUS),
            -model.data(index, core.ROLE_PRIORITY),
            model.lastModified(index).toPython())
