# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os

from Qt.QtCore import QDir, QSortFilterProxyModel, Qt
from Qt.QtGui import QBrush, QColor
from Qt.QtWidgets import QFileSystemModel
from six.moves import range

from . import filetools

ROLE_PRIORITY = Qt.UserRole + 4
ROLE_RANGE = Qt.UserRole + 5
ROLE_STATUS = Qt.UserRole + 6
ROLE_REMAINS = Qt.UserRole + 7
ROLE_ESTIMATE = Qt.UserRole + 8
ROLE_FRAMES = Qt.UserRole + 9
ROLE_FILE = Qt.UserRole + 10
ROLE_ERROR_COUNT = Qt.UserRole + 11

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
            i: {} for i in
            (Qt.CheckStateRole,
             Qt.ToolTipRole,
             Qt.StatusTipRole,
             Qt.ForegroundRole,
             ROLE_PRIORITY,
             ROLE_RANGE,
             ROLE_STATUS,
             ROLE_REMAINS,
             ROLE_ESTIMATE,
             ROLE_FRAMES,
             ROLE_FILE,
             ROLE_ERROR_COUNT)
        }

        self.header_roles = (
            self.FileNameRole, ROLE_RANGE, ROLE_PRIORITY)
        self._data_redirect_get = {
            Qt.CheckStateRole: self._get_check_state_data,
            Qt.ForegroundRole: self._get_foreground_data,
            Qt.BackgroundRole: self._get_background_data,
        }

    def columnCount(self, parent):
        """Override.  """
        # pylint: disable=unused-argument

        return len(self.header_roles)

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

        redirect = self._data_redirect_get

        if role in redirect:
            return redirect[role](index)
        elif role in self.columns:
            key = self._data_key(index)
            return self.columns[role].get(key, _column_default(index, role))
        elif role in (Qt.DisplayRole, Qt.EditRole):
            return self._custom_data(index, role)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter
        return super(DirectoryModel, self).data(index, role)

    def _get_check_state_data(self, index):
        if index.column() != 0:
            return None

        return Qt.Unchecked if self.data(
            index, ROLE_STATUS) & DISABLED else Qt.Checked

    def setData(self, index, value, role=Qt.EditRole):
        """Override.  """

        if role == Qt.CheckStateRole:
            return self._set_check_state_data(index, value)

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

    def _get_foreground_data(self, index):
        status = self.data(index, ROLE_STATUS)
        if status & DOING:
            return QBrush(QColor(Qt.white))
        elif status & FINISHED:
            return QBrush(QColor(Qt.gray))
        return QBrush(QColor(Qt.black))

    def _get_background_data(self, index):
        status = self.data(index, ROLE_STATUS)
        if status & DOING:
            return QBrush(QColor(30, 40, 45))
        elif status & DISABLED:
            return QBrush(QColor(Qt.gray))

        return QBrush(QColor(Qt.white))

    def _set_check_state_data(self, index, value):
        status = self.data(index, ROLE_STATUS)
        if value == Qt.Checked:
            status &= ~DISABLED
        else:
            status |= DISABLED

        self.setData(index, status, ROLE_STATUS)
        return True

    def _data_key(self, index):
        return super(DirectoryModel, self).data(index, self.FilePathRole)

    def _custom_data(self, index, role):
        column_index = index.column()
        role = self.header_roles[column_index]
        if role in self.columns:
            return self.data(index, role)
        return super(DirectoryModel, self).data(index, role)


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

    def indexes(self):
        """Return all indexes under root.  """

        root_index = self.root_index()
        count = self.rowCount(root_index)
        return (self.index(i, 0, root_index) for i in range(count))

    def absolute_path(self, *path):
        """Convert path to absolute path.  """
        model = self.sourceModel()
        return os.path.abspath(os.path.join(model.rootPath(), *path))

    def checked_files(self):
        """Iterator for checked files in model.  """

        return (self.file_path(i)
                for i in self.indexes()
                if self.data(i, Qt.CheckStateRole))

    def all_files(self):
        """Iterator for all files in model.  """

        return (self.file_path(i)
                for i in self.indexes())

    def old_version_files(self):
        """Files that has a lower version number.  """

        files = self.all_files()
        return (i for i in files if i not in filetools.version_filter(files))


def _get_sort_data(model, index):
    return (model.data(index, Qt.CheckStateRole),
            model.data(index, ROLE_STATUS),
            -model.data(index, ROLE_PRIORITY),
            model.lastModified(index).toPython())


def _column_default(index, role):
    defaults = {
        ROLE_PRIORITY: 0,
        ROLE_RANGE: '',
        ROLE_STATUS: 0b0,
    }
    if index.column() == 0:
        defaults[Qt.CheckStateRole] = Qt.Checked
    return defaults.get(role)
