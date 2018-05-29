# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import logging
from Qt.QtCore import QDir, QPersistentModelIndex, Qt, QSortFilterProxyModel
from Qt.QtWidgets import QFileSystemModel
from six.moves import range

ROLE_PRIORITY = Qt.UserRole + 4
ROLE_RANGE = Qt.UserRole + 5
ROLE_STATUS = Qt.UserRole + 6

# Task state bitmask
DOING = 1 << 0
DISABLED = 1 << 1
FINISHED = 1 << 2

LOGGER = logging.getLogger(__name__)


class DirectoryModel(QFileSystemModel):
    """Checkable fileSystem model.  """

    def __init__(self, parent=None):
        super(DirectoryModel, self).__init__(parent)
        self.setFilter(QDir.Files)
        self.columns = {
            Qt.CheckStateRole: {},
            Qt.ToolTipRole: {},
            Qt.StatusTipRole: {},
            Qt.ForegroundRole: {},
            ROLE_PRIORITY: {},
            ROLE_RANGE: {},
            ROLE_STATUS: {},
        }

        self.header_roles = (
            self.FileNameRole, ROLE_RANGE, ROLE_PRIORITY)
        self.insertColumn(0)
        self.insertColumn(1)
        self.insertColumn(1)

    def columnCount(self, parent):
        """Override.  """

        return len(self.header_roles)

    # def roleNames(self):
    #     ret = super(DirectoryModel, self).roleNames()
    #     ret.update({
    #         ROLE_PRIORITY: b'priority',
    #         ROLE_STATUS: b'status',
    #     }
    #     )
    #     return ret
    def _data_key(self, index):
        return super(DirectoryModel, self).data(index, self.FilePathRole)

    def flags(self, index):
        """Override.  """

        ret = super(DirectoryModel, self).flags(index)
        column = index.column()
        if column in (0,):
            ret |= Qt.ItemIsUserCheckable
        if column in (1, 2):
            ret |= Qt.ItemIsEditable
        return ret

    def data(self, index, role=Qt.DisplayRole):
        """Override.  """

        key = self._data_key(index)
        if role == Qt.CheckStateRole and index.column() != 0:
            return None
        elif role in self.columns:
            return self.columns[role].get(key, _column_default(index, role))
        elif role in (Qt.DisplayRole, Qt.EditRole):
            return self._custom_data(index, role)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter
        return super(DirectoryModel, self).data(index, role)

    def setData(self, index, value, role=Qt.EditRole):
        """Override.  """

        key = self._data_key(index)
        column = index.column()
        if (index.isValid()
                and column <= len(self.header_roles)
                and role in (Qt.DisplayRole, Qt.EditRole)):
            role = self.header_roles[index.column()]
        if role in self.columns:
            self.columns[role][key] = value
            self.dataChanged.emit(index, index)
            return True
        return super(DirectoryModel, self).setData(index, value, role)

    def _custom_data(self, index, role):
        column_index = index.column()
        role = self.header_roles[column_index]
        if role in self.columns:
            return self.data(index, role)
        return super(DirectoryModel, self).data(index, role)

    def all_file(self):
        """All files under root.  """

        root_index = self.index(self.rootPath())
        return [self.data(self.index(i, 0, root_index)) for i in range(self.rowCount(root_index))]


def _column_default(index, role):
    defaults = {
        ROLE_PRIORITY: 0,
        ROLE_RANGE: '',
    }
    if index.column() == 0:
        defaults[Qt.CheckStateRole] = Qt.Unchecked
    return defaults.get(role)


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

    def all_files(self):
        """All files in display.  """

        root_index = self.root_index()
        count = self.rowCount(root_index)
        return [self.data(self.index(i, 0, root_index)) for i in range(count)]

    def checked_files(self):
        """All checked files.  """

        root_index = self.root_index()
        count = self.rowCount(root_index)
        ret = []
        for i in range(count):
            index = self.index(i, 0, root_index)
            if self.data(index, Qt.CheckStateRole):
                data = self.data(index)
                ret.append(data)
        return ret

    def lessThan(self, left, right):
        """Override.  """

        def _get_sort_data(model, index):
            return (model.data(index, Qt.CheckStateRole),
                    model.data(index, ROLE_STATUS),
                    model.data(index, ROLE_PRIORITY),
                    model.lastModified(index).toPython())

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

            return [
                {
                    Qt.DisplayRole: '文件',
                },
                {
                    Qt.DisplayRole: '范围',
                },
                {
                    Qt.DisplayRole: '优先级',
                },
            ][section][role]
        except (KeyError, IndexError):
            return super(FilesProxyModel, self).headerData(
                section, orientation, role)

    def root_index(self):
        """Index of root path.  """

        model = self.sourceModel()
        return self.mapFromSource(model.index(model.rootPath()))

    def absolute_path(self, *path):
        """Convert path to absolute path.  """
        model = self.sourceModel()
        return os.path.abspath(os.path.join(model.rootPath(), *path))

    def is_dir(self, index):
        """Wrapper for `self.sourceModel().isDir`.  """

        source_index = self.mapToSource(index)
        source_model = self.sourceModel()
        return source_model.isDir(source_index)

    def indexes(self):
        """Return all indexes under root.  """

        root_index = self.root_index()
        count = self.rowCount(root_index)
        return (self.index(i, 0, root_index) for i in range(count))

    def file_path(self, index):
        """Wrapper for `self.sourceModel().filePath`.  """

        index = self.mapToSource(index)
        return self.sourceModel().filePath(index)

    def source_index(self, path):
        """Get source model index from path.

        Args:
            path (str): Path data.

        Returns:
            Qt.QtCore.ModelIndex: Index in source model.
        """

        source_model = self.sourceModel()
        return self.mapFromSource(source_model.index(path))
