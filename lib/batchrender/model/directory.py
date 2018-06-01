# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from Qt.QtCore import QDir, Qt
from Qt.QtGui import QBrush, QColor
from Qt.QtWidgets import QFileSystemModel

from . import core


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
             core.ROLE_PRIORITY,
             core.ROLE_RANGE,
             core.ROLE_STATE,
             core.ROLE_REMAINS,
             core.ROLE_ESTIMATE,
             core.ROLE_FRAMES,
             core.ROLE_FILE,
             core.ROLE_ERROR_COUNT)
        }

        self.header_roles = (
            self.FileNameRole, core.ROLE_RANGE, core.ROLE_PRIORITY)
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
            index, core.ROLE_STATE) & core.DISABLED else Qt.Checked

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
        status = self.data(index, core.ROLE_STATE)
        if status & core.PARTIAL:
            return QBrush(QColor(150, 200, 235))
        elif status & core.DOING:
            return QBrush(QColor(Qt.white))
        elif status & core.FINISHED:
            return QBrush(QColor(Qt.gray))
        return QBrush(QColor(Qt.black))

    def _get_background_data(self, index):
        status = self.data(index, core.ROLE_STATE)
        if status & core.DOING:
            return QBrush(QColor(30, 40, 45))
        elif status & core.DISABLED:
            return QBrush(QColor(Qt.gray))

        return QBrush(QColor(Qt.white))

    def _set_check_state_data(self, index, value):
        status = self.data(index, core.ROLE_STATE)
        if value == Qt.Checked:
            status &= ~core.DISABLED
        else:
            status |= core.DISABLED

        self.setData(index, status, core.ROLE_STATE)
        return True

    def _data_key(self, index):
        return super(DirectoryModel, self).data(index, self.FilePathRole)

    def _custom_data(self, index, role):
        column_index = index.column()
        role = self.header_roles[column_index]
        if role in self.columns:
            return self.data(index, role)
        return super(DirectoryModel, self).data(index, role)


def _column_default(index, role):
    defaults = {
        core.ROLE_PRIORITY: 0,
        core.ROLE_RANGE: '',
        core.ROLE_STATE: 0b0,
        core.ROLE_ERROR_COUNT: 0,
    }
    if index.column() == 0:
        defaults[Qt.CheckStateRole] = Qt.Checked
    return defaults.get(role)
