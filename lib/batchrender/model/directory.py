# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import pendulum
from Qt.QtCore import QDir, Qt
from Qt.QtGui import QBrush, QColor
from Qt.QtWidgets import QFileSystemModel

from . import core
from ..codectools import get_unicode as u
from ..framerange import FrameRange
from ..mixin import UnicodeTrMixin


class DirectoryModel(UnicodeTrMixin, QFileSystemModel):
    """Checkable fileSystem model.  """

    def __init__(self, parent=None):
        super(DirectoryModel, self).__init__(parent)
        self.setFilter(QDir.Files)
        self.columns = {
            i: {} for i in
            (Qt.StatusTipRole,
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
        self._data_react_get = {
            Qt.ToolTipRole: self.tooltip_html
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
        react = self._data_react_get
        if role in redirect:
            return redirect[role](index)
        elif role in react:
            return react[role](index)
        elif role in self.columns:
            key = self._data_key(index)
            return self.columns[role].get(key, _column_default(index, role))
        elif role in (Qt.DisplayRole, Qt.EditRole):
            return self._custom_data(index)
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter
        return super(DirectoryModel, self).data(index, role)

    def tooltip_html(self, index):
        """Tooltip html for UI.  """

        row_template = '<tr><td>{}</td><td align="right">{}</td></tr>'

        def _row(label, value):
            value = ('<i>{}</i>'.format(self.tr('NO DATA'))
                     if value is None else value)
            return row_template.format(label, value)

        def _timef(seconds):
            if seconds is None:
                return None
            return pendulum.duration(seconds=seconds).in_words()

        file_record = self.data(index, core.ROLE_FILE)
        state = self.data(index, core.ROLE_STATE)
        remains = self.data(index, core.ROLE_REMAINS)
        estimate = self.data(index, core.ROLE_ESTIMATE)
        label = self.data(index, Qt.DisplayRole)

        rows = ['<tr><th colspan=2>{}</th></tr>'.format(label),
                _row(self.tr('Estimate cost'), _timef(estimate)), ]
        if file_record:
            rows.extend(
                [
                    _row(self.tr('File hash'), file_record.hash),
                    _row(self.tr('Frame count'), file_record.frame_count),
                    _row(self.tr('File range'), file_record.range()),
                    _row(self.tr('Average frame cost'), _timef(
                        file_record.average_frame_cost())),
                ]
            )
        if state & core.DOING and remains:
            rows.append(_row(self.tr('Remains'), _timef(remains)))

        return '<table>{}</table>'.format(''.join(rows))

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
            self.columns[role][key] = self._parse_data(
                value, role, _column_default(index, role))
            self.dataChanged.emit(index, index)
            return True
        return super(DirectoryModel, self).setData(index, value, role)

    @staticmethod
    def _parse_data(value, role, default):
        try:
            if role == core.ROLE_RANGE and not isinstance(value, FrameRange):
                value = FrameRange.parse(value)
            return value
        except (ValueError, AttributeError):
            return default

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
        if status & core.DOING:
            return False
        elif value == Qt.Checked:
            status &= ~core.DISABLED
            file_ = self.data(index, core.ROLE_FILE)
            if file_.is_rendering():
                file_.remove_tempfile()
        else:
            status |= core.DISABLED

        self.setData(index, status, core.ROLE_STATE)
        return True

    def _data_key(self, index):
        return super(DirectoryModel, self).data(index, self.FilePathRole)

    def _custom_data(self, index):
        column_index = index.column()
        role = self.header_roles[column_index]
        if role in self.columns:
            ret = self.data(index, role)
            return self._format_custom_data(ret)
        return super(DirectoryModel, self).data(index, role)

    def _format_custom_data(self, value):
        if isinstance(value, FrameRange):
            value = u(value)
        return value


def _column_default(index, role):
    defaults = {
        core.ROLE_PRIORITY: 0,
        core.ROLE_RANGE: None,
        core.ROLE_STATE: 0b0,
        core.ROLE_ERROR_COUNT: 0,
    }
    if index.column() == 0:
        defaults[Qt.CheckStateRole] = Qt.Checked
    return defaults.get(role)
