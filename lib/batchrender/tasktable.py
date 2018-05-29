# -*- coding=UTF-8 -*-
"""GUI tasktable.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import webbrowser

from Qt.QtCore import QObject, Qt, QTimer, Slot
from Qt.QtGui import QBrush, QColor
from Qt.QtWidgets import QTableWidgetItem

from . import render
from .database import DATABASE
from .files import FILES

LOGGER = logging.getLogger()


class Row(QObject):
    """Single row."""

    brushes = {
        None: (QBrush(QColor(Qt.white)),
               QBrush(QColor(Qt.black))),
        render.core.DOING: (QBrush(QColor(30, 40, 45)),
                            QBrush(QColor(Qt.white))),
        render.core.DISABLED: (QBrush(QColor(Qt.gray)),
                               QBrush(QColor(Qt.black))),
        render.core.FINISHED: (QBrush(QColor(Qt.white)),
                               QBrush(QColor(Qt.gray)))
    }
    flags = {None: ((Qt.ItemIsSelectable | Qt.ItemIsEnabled
                     | Qt.ItemIsUserCheckable),
                    (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                     | Qt.ItemIsEditable)),
             render.core.DOING: ((Qt.ItemIsSelectable | Qt.ItemIsEnabled
                                  | Qt.ItemIsUserCheckable),
                                 (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                                  | Qt.ItemIsEditable)),
             render.core.DISABLED: ((Qt.ItemIsEnabled | Qt.ItemIsSelectable
                                     | Qt.ItemIsUserCheckable),
                                    (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                                     | Qt.ItemIsEditable)),
             render.core.FINISHED: ((Qt.ItemIsSelectable | Qt.ItemIsEnabled),
                                    (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                                     | Qt.ItemIsEditable))}
    _task = None
    updating = False

    def __init__(self):
        super(Row, self).__init__()
        self.columns = [QTableWidgetItem() for _ in range(2)]
        self._add_itemdata_type_check(self.columns[1], int)

    def __str__(self):
        ret = ' '.join('({},{})'.format(i.row(), i.column()) for i in self)
        ret = '<Row {}>'.format(ret)
        return ret

    def __getitem__(self, index):
        return self.columns[index]

    def __len__(self):
        return len(self.columns)

    @property
    def task(self):
        """Task in this row.  """
        return self._task

    @task.setter
    def task(self, value):
        assert isinstance(value, render.Task)
        if self._task:
            self._task.changed.disconnect(self.update)
            self._task.progressed.disconnect(self.update)
        value.changed.connect(self.update)
        value.progressed.connect(self.update)
        self._task = value
        self.update()

    @staticmethod
    def _add_itemdata_type_check(item, data_type):
        assert isinstance(item, QTableWidgetItem)

        def _set_data(index, value):
            if index == 2:
                try:
                    data_type(value)
                except ValueError:
                    LOGGER.debug('invaild value: %s', value)
                    return
            QTableWidgetItem.setData(
                item, index, value)
        item.setData = _set_data

    @Slot()
    def update(self):
        """Update row by task."""

        task = self.task
        if not task or self.updating:
            return
        assert isinstance(task, render.Task)

        self.updating = True

        def _choice():
            choice = None
            for state in (render.core.FINISHED, render.core.DOING, render.core.DISABLED):
                if state & self.task.state:
                    choice = state
                    break
            return choice

        def _stylize(item):
            """Set item style. """

            choice = _choice()
            item.setBackground(self.brushes[choice][0])
            item.setForeground(self.brushes[choice][1])

        # LOGGER.debug('update row: %s', self.task)
        assert all(isinstance(i, QTableWidgetItem) for i in self)
        name = self.columns[0]
        priority = self.columns[1]

        name.setText(self.task.filename)
        name.setCheckState(Qt.CheckState(
            0 if self.task.state & render.core.DISABLED else 2))
        name.setFlags(self.flags[_choice()][0])

        priority.setText(str(self.task.priority))
        priority.setFlags(self.flags[_choice()][1])

        _stylize(name)
        _stylize(priority)

        row_format = '<tr><td>{}</td><td align="right">{}</td></tr>'
        _row = row_format.format
        avg = DATABASE.get_averge_time(task.filename)
        none_str = '<i>无统计数据</i>'
        rows = ['<tr><th colspan=2>{}</th></tr>'.format(task.filename),
                _row('帧数', task.frames or none_str),
                _row('帧均耗时', render.core.timef(int(avg)) if avg else none_str),
                _row('预计耗时', render.core.timef(int(task.estimate_time)))]
        if task.state & render.core.DOING and task.remains:
            rows.append(
                _row('剩余时间', render.core.timef(int(task.remains))))
        tooltip = '<table>{}</table>'.format(''.join(rows))

        name.setToolTip(tooltip)

        self.updating = False


class TaskTable(QObject):
    """Table widget.  """

    def __init__(self, widget, parent):
        super(TaskTable, self).__init__(parent)
        self._rows = []
        self.widget = widget
        self.parent = parent
        self.queue = self.parent.queue
        assert isinstance(self.queue, render.Queue)

        self.widget.setColumnWidth(0, 350)
        self.queue.changed.connect(self.on_queue_changed)

        self.parent.pushButtonRemoveOldVersion.clicked.connect(
            self.remove_old_version)
        self.parent.toolButtonCheckAll.clicked.connect(self.check_all)
        self.parent.toolButtonReverseCheck.clicked.connect(self.reverse_check)
        self.parent.toolButtonRemove.clicked.connect(self.remove_selected)

        self.widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.widget.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.widget.cellChanged.connect(self.on_cell_changed)

        # Timer for widget update
        _timer = QTimer(self)
        _timer.timeout.connect(self.update_queue)
        _timer.start(1000)

    def __getitem__(self, index):
        if not isinstance(index, int):
            return [i for i in self._rows if i.task == index][0]
        return self._rows[index]

    def __delitem__(self, index):
        del self._rows[index]

    def __len__(self):
        return len(self._rows)

    def append(self, row):
        """Add row to last.  """
        assert isinstance(row, Row)
        row.updating = True

        index = len(self._rows)
        self._rows.append(row)
        for column, item in enumerate(row):
            self.widget.setItem(index, column, item)

        row.updating = False

    def set_row_count(self, number):
        """Set row count number.  """

        change = number - len(self)
        if change > 0:
            self.widget.setRowCount(number)
            for _ in xrange(change):
                self.append(Row())
        elif change < 0:
            self.widget.setRowCount(number)
            del self[number:]

    def update_queue(self):
        """Update queue to match files.  """

        FILES.update()
        map(self.queue.put, FILES)

    def on_queue_changed(self):
        """Update table to match task queue.  """

        self.set_row_count(len(self.queue))
        for index, task in enumerate(self.queue):
            row = self[index]
            assert isinstance(row, Row)
            row.task = task

    @Slot(int, int)
    def on_cell_changed(self, row, column):
        """Callback on cell changed.  """
        if self[row].updating:
            return

        item = self.widget.item(row, column)
        task = self.queue[row]

        if column == 0:
            if item.checkState():
                task.state &= ~render.core.DISABLED
            else:
                task.state |= render.core.DISABLED
        elif column == 1:
            try:
                text = item.text()
                task.priority = int(text)
            except ValueError:
                LOGGER.error('不能识别优先级 %s, 重置为%s', text, task.priority)
                item.setText(unicode(task.priority))

    @Slot(int, int)
    def on_cell_double_clicked(self, row, column):
        if column != 0:
            return

        task = self[row].task
        path = os.path.dirname(task.filename) or '.'
        LOGGER.debug('User clicked: %s', task)
        webbrowser.open(path)

    def on_selection_changed(self):
        """Do work on selection changed.  """

        tasks = (i for i in self.current_selected() if not i.state &
                 render.core.DOING)
        self.parent.toolButtonRemove.setEnabled(any(tasks))

    @property
    def checked_files(self):
        """Return files checked in listwidget.  """
        return (i.text() for i in self.items() if i.checkState())

    def items(self):
        """Item in list widget -> list."""

        widget = self.widget
        return list(widget.item(i, 0) for i in xrange(widget.rowCount()))

    def remove_old_version(self):
        """Remove all old version nk files.  """

        files = FILES.old_version_files()
        if not files:
            return

        LOGGER.info('移除较低版本号文件: %s', files)
        for i in files:
            self.queue.remove(i)

    def check_all(self):
        """Check all item.  """

        for row in self:
            task = row.task
            assert isinstance(task, render.Task)
            task.state &= ~render.core.DISABLED

    def reverse_check(self):
        """Reverse checkstate for every item.  """

        tasks = [i.task for i in self]
        for task in tasks:
            assert isinstance(task, render.Task)
            task.state ^= render.core.DISABLED

    def current_selected(self):
        """Current selected tasks.  """

        rows = set()
        _ = [rows.add(i.row()) for i in self.widget.selectedItems()]
        ret = [self[i].task for i in rows]
        # LOGGER.debug('\n\tCurrent selected: %s',
        #              ''.join(['\n\t\t{}'.format(i) for i in ret]) or '<None>')
        return ret

    def remove_selected(self):
        """Select all item in list widget.  """

        tasks = [i for i in self.current_selected() if not i.state &
                 render.core.DOING]

        for i in tasks:
            self.queue.remove(i)
