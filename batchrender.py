#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""
# TODO: Add task detail to table item tooltip.
from __future__ import print_function, unicode_literals

import atexit
import logging
import logging.handlers
import os
import subprocess
import sys
import webbrowser

import render
import singleton
from config import CONFIG
from log import MultiProcessingHandler
from path import get_unicode

if __name__ == '__main__':
    __SINGLETON = singleton.SingleInstance()

try:
    from Qt import QtCompat, QtCore, QtWidgets, QtGui
    from Qt.QtWidgets import QApplication, QFileDialog, QMainWindow
except:
    raise

__version__ = '0.8.10'


LOGGER = logging.getLogger()


def _set_logger():
    logger = logging.getLogger()
    logger.propagate = False

    # Stream handler
    _handler = MultiProcessingHandler(logging.StreamHandler)
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]:%(filename)s:%(lineno)d: %(message)s', '%H:%M:%S')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.debug('Added stream handler.  ')

    # File handler
    path = CONFIG.log_path
    _handler = MultiProcessingHandler(
        logging.handlers.RotatingFileHandler,
        args=(path,), kwargs={'backupCount': 5})
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]:%(name)s: %(message)s', '%x %X')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

    # Loglevel
    loglevel = os.getenv('LOGLEVEL', logging.INFO)
    try:
        logger.setLevel(int(loglevel))
    except TypeError:
        logger.warning(
            'Can not recognize env:LOGLEVEL %s, expect a int', loglevel)

    if os.stat(path).st_size > 10000:
        try:
            _handler.doRollover()
        except OSError:
            LOGGER.debug('Rollover log file failed.')


if __name__ == '__main__':
    _set_logger()
del _set_logger

if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)


if sys.getdefaultencoding() != 'UTF-8':
    reload(sys)
    sys.setdefaultencoding('UTF-8')


class Application(QApplication):
    """QApplication subclass. """

    def notify(self, reciever, event):
        """(Overrride)  """

        try:
            return super(Application, self).notify(reciever, event)
        except Exception as ex:
            LOGGER.error(ex)
            raise
        return False


class MainWindow(QMainWindow):
    """Main GUI window.  """
    render_pool = None
    render_started = QtCore.Signal()
    render_stopped = QtCore.Signal()

    class Title(object):
        """Window title.  """
        default_title = 'Nuke批渲染'
        prefix = ''
        title_index = 0

        def __init__(self, parent):
            self.title_index = 0
            assert isinstance(
                parent, MainWindow), 'Need a Mainwindow as parent.'
            self.parent = parent

            self._timer = QtCore.QTimer()
            self._timer.setInterval(300)
            self._timer.timeout.connect(self.update)
            setattr(self.parent, '_title', self)

            self.parent.render_stopped.connect(self.update_prefix)
            self.parent.task_table.queue_changed.connect(self.update_prefix)
            self.parent.progressBar.valueChanged.connect(self.update_prefix)

            self.parent.render_started.connect(self._timer.start)
            self.parent.render_stopped.connect(self._timer.stop)

            self.update()

        def update_prefix(self):
            """Update title prefix with progress.  """
            prefix = ''
            queue_length = len(self.parent.task_table.queue)

            if queue_length:
                prefix = '[{}]{}'.format(queue_length, prefix)
            if self.parent.is_rendering:
                prefix = '{}%{}'.format(
                    self.parent.progressBar.value(), prefix)

            if prefix != self.prefix:
                self.prefix = prefix
                self.update()

        def update(self):
            """Update title, rotate when rendering.  """

            if self.parent.is_rendering:
                title = self.parent.render_pool.current_task.partition('.nk')[
                    0] or self.default_title
                self.title_index += 1
                index = self.title_index % len(title)
            else:
                title = self.default_title
                self.title_index = 0
                index = 0

            title = '{}{} {}'.format(
                self.prefix, title[index:], title[:index])

            self.parent.setWindowTitle(title)

    def __init__(self, parent=None):
        def _signals():
            self.lineEditDir.textChanged.connect(self.check_dir)
            self.comboBoxAfterFinish.currentIndexChanged.connect(
                self.on_after_render_changed)

            self.toolButtonAskDir.clicked.connect(self.ask_dir)
            self.toolButtonOpenDir.clicked.connect(
                lambda: webbrowser.open(CONFIG['DIR']))
            self.toolButtonOpenLog.clicked.connect(
                lambda: webbrowser.open(CONFIG.log_path))

            self.pushButtonStart.clicked.connect(self.start_button_clicked)
            self.pushButtonStop.clicked.connect(self.stop_button_clicked)
            self.pushButtonRemoveOldVersion.clicked.connect(
                lambda: render.Files().remove_old_version())

            self.textBrowser.anchorClicked.connect(open_path)

            self.render_started.connect(lambda: self.progressBar.setValue(0))
            self.render_stopped.connect(self.on_render_stopped)

            self.task_table.queue_changed.connect(self.on_queue_changed)

        def _edits():
            for edit, key in self.edits_key.iteritems():
                if isinstance(edit, QtWidgets.QLineEdit):
                    edit.setText(CONFIG.get(key, ''))
                    edit.editingFinished.connect(
                        lambda edit=edit, k=key: CONFIG.__setitem__(k, edit.text()))
                elif isinstance(edit, QtWidgets.QCheckBox):
                    edit.setCheckState(
                        QtCore.Qt.CheckState(CONFIG.get(key, 0)))
                    edit.stateChanged.connect(
                        lambda state, k=key: CONFIG.__setitem__(k, state))
                elif isinstance(edit, QtWidgets.QComboBox):
                    edit.setCurrentIndex(CONFIG.get(key, 0))
                    edit.currentIndexChanged.connect(
                        lambda index, k=key: CONFIG.__setitem__(k, index))
                else:
                    LOGGER.debug('待处理的控件: %s %s', type(edit), edit)

        def _icon():
            _stdicon = self.style().standardIcon

            _icon = _stdicon(QtWidgets.QStyle.SP_MediaPlay)
            self.setWindowIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DirOpenIcon)
            self.toolButtonOpenDir.setIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DialogOpenButton)
            self.toolButtonAskDir.setIcon(_icon)

        QMainWindow.__init__(self, parent)
        self.queue = render.Queue()

        # ui
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../batchrender.ui')))
        self.setCentralWidget(self._ui)
        self.task_table = TaskTable(self.tableWidget, self)
        self.Title(self)
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.labelVersion.setText('v{}'.format(__version__))
        _icon()
        self.resize(500, 700)

        # Connect edit to config
        self.edits_key = {
            self.lineEditDir: 'DIR',
            self.checkBoxProxy: 'PROXY',
            self.checkBoxPriority: 'LOW_PRIORITY',
            self.checkBoxContinue: 'CONTINUE',
            self.comboBoxAfterFinish: 'AFTER_FINISH',
        }
        _edits()

        self.new_render_pool()

        _signals()

    def __getattr__(self, name):
        return getattr(self._ui, name)

    @property
    def is_rendering(self):
        """If render runing.  """
        return self.render_pool and self.render_pool.isRunning()

    def on_render_stopped(self):
        """Do work when rendering stop.  """

        after_finish = self.comboBoxAfterFinish.currentText()
        actions = {
            '什么都不做': lambda: LOGGER.info('渲染完成后什么都不做'),
            '休眠': hiber,
            '关机': shutdown,
            'Deadline': lambda: webbrowser.open(CONFIG['DEADLINE']),
            '执行命令': lambda: subprocess.Popen(CONFIG['AFTER_FINISH_CMD'], shell=True),
            '运行程序': lambda: webbrowser.open(CONFIG['AFTER_FINISH_PROGRAM']),
        }

        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.pushButtonStart.show()
        self.pushButtonRemoveOldVersion.setEnabled(True)

        for task in self.queue:
            if task.is_doing:
                task.is_doing = False
                self.task_table[self.queue.index(task)].update()
        self.tabWidget.setCurrentIndex(0)

        Application.alert(self)

        self.new_render_pool()
        LOGGER.info('渲染结束')

        actions.get(after_finish, lambda: LOGGER.error(
            'Not found match action for %s', after_finish))()

    def on_queue_changed(self):
        """Do work when task queue changed.  """

        LOGGER.debug('On task table changed.')
        if self.task_table.queue:
            self.pushButtonStart.setEnabled(True)
        else:
            self.pushButtonStart.setEnabled(False)

    def on_after_render_changed(self):
        """Do work when comboBoxAfterFinish changed.  """
        edit = self.comboBoxAfterFinish
        text = edit.currentText()
        LOGGER.debug('After render change to %s', text)

        def _reset():
            edit.setCurrentIndex(0)

        if text == 'Deadline':
            if os.path.exists(CONFIG['DEADLINE']):
                LOGGER.info('渲染后运行Deadline: %s', CONFIG['DEADLINE'])
                return
            path = QFileDialog.getOpenFileName(
                self,
                '选择Deadline Slave执行程序',
                dir=CONFIG['DEADLINE'],
                filter='deadlineslave.exe;;*.*',
                selectedFilter='deadlineslave.exe')[0]
            if path:
                CONFIG['DEADLINE'] = path
                LOGGER.info('Deadline 路径改为: %s', path)
                edit.setToolTip(path)
            else:
                _reset()
        elif text == '执行命令':
            cmd, confirm = QtWidgets.QInputDialog.getText(
                self, '执行命令', '命令内容', text=CONFIG['AFTER_FINISH_CMD'])
            if confirm and cmd:
                CONFIG['AFTER_FINISH_CMD'] = cmd
                LOGGER.info('渲染后执行命令: %s', cmd)
                edit.setToolTip(cmd)
            else:
                _reset()
        elif text == '运行程序':
            path = QFileDialog.getOpenFileName(
                self, '渲染完成后运行...', dir=CONFIG['AFTER_FINISH_PROGRAM'])[0]
            if path:
                CONFIG['AFTER_FINISH_PROGRAM'] = path
                LOGGER.info('渲染后运行程序: %s', cmd)
                edit.setToolTip(path)
            else:
                _reset()
        else:
            edit.setToolTip('')

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        path = QFileDialog.getExistingDirectory(
            dir=os.path.dirname(CONFIG['DIR']))
        if path:
            if self.check_dir(path):
                CONFIG['DIR'] = path
            else:
                self.ask_dir()

    def check_dir(self, path):
        """Check if dir is nuke readable.  """

        edit = self.lineEditDir
        path = path or edit.text()
        try:
            path.encode('ascii')
            if os.path.exists(path):
                edit.setStyleSheet('')
            else:
                edit.setStyleSheet('background:rgb(100%,50%,50%)')
        except UnicodeEncodeError:
            edit.setText(CONFIG['DIR'])
            QtWidgets.QMessageBox.information(
                self, path, 'Nuke只支持英文路径')
            return False
        return True

    def new_render_pool(self):
        """Switch to new render pool.  """
        LOGGER.debug('New render pool.')
        self.render_pool = render.Pool(self.task_table.queue)
        self.render_pool.stdout.connect(self.textBrowser.append)
        self.render_pool.stderr.connect(self.textBrowser.append)
        self.render_pool.progress.connect(self.progressBar.setValue)
        self.render_pool.task_started.connect(self.task_table.update_widget)
        self.render_pool.task_finished.connect(self.task_table.update_widget)
        self.render_pool.queue_finished.connect(self.render_stopped.emit)

    def start_button_clicked(self):
        """Button clicked action.  """

        self.tabWidget.setCurrentIndex(1)
        self.pushButtonRemoveOldVersion.setEnabled(False)

        start_error_handler()
        self.render_pool.start()

        self.render_started.emit()

    def stop_button_clicked(self):
        """Button clicked action.  """
        self.comboBoxAfterFinish.setCurrentIndex(0)

        self.render_pool.stop()

        self.render_stopped.emit()

    def closeEvent(self, event):
        """Override qt closeEvent."""

        if self.is_rendering:
            confirm = QtWidgets.QMessageBox.question(
                self,
                '正在渲染中',
                "停止渲染并退出?",
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if confirm == QtWidgets.QMessageBox.Yes:
                self.render_pool.stop()
                Application.exit()
                LOGGER.info('渲染途中退出')
            else:
                event.ignore()
        else:
            Application.exit()
            LOGGER.info('退出')


@QtCore.Slot(QtCore.QUrl)
def open_path(q_url):
    """Open file in console.  """
    path = q_url.toString()
    if not os.path.exists(path):
        path = os.path.dirname(path)
    webbrowser.open(path)


def start_error_handler():
    """Start error dialog handle for windows.  """
    if sys.platform == 'win32':
        _file = os.path.abspath(os.path.join(__file__, '../error_handler.exe'))
        proc = subprocess.Popen(_file)
        atexit.register(proc.terminate)


class TaskTable(QtCore.QObject):
    """Table widget.  """
    queue_changed = QtCore.Signal()

    class Row(list):
        """Single row."""
        brushes = {
            'waiting': (QtGui.QBrush(QtGui.QColor(QtCore.Qt.white)),
                        QtGui.QBrush(QtGui.QColor(QtCore.Qt.black))),
            'doing': (QtGui.QBrush(QtGui.QColor(30, 40, 45)),
                      QtGui.QBrush(QtGui.QColor(QtCore.Qt.white))),
            'disabled': (QtGui.QBrush(QtGui.QColor(QtCore.Qt.gray)),
                         QtGui.QBrush(QtGui.QColor(QtCore.Qt.black))),
            'finished': (QtGui.QBrush(QtGui.QColor(QtCore.Qt.white)),
                         QtGui.QBrush(QtGui.QColor(QtCore.Qt.gray)))
        }
        flags = {'waiting': ((QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
                              | QtCore.Qt.ItemIsUserCheckable),
                             (QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                              | QtCore.Qt.ItemIsEditable)),
                 'doing': ((QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
                            | QtCore.Qt.ItemIsUserCheckable),
                           (QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                            | QtCore.Qt.ItemIsEditable)),
                 'disabled': ((QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                               | QtCore.Qt.ItemIsUserCheckable),
                              (QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                               | QtCore.Qt.ItemIsEditable)),
                 'finished': ((QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled),
                              (QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable))}
        task = None
        updating = False

        def __init__(self):
            column = [QtWidgets.QTableWidgetItem() for _ in range(2)]
            super(TaskTable.Row, self).__init__(column)

        def __str__(self):
            ret = ' '.join('({},{})'.format(i.row(), i.column()) for i in self)
            ret = '<Row {}>'.format(ret)
            return ret

        def update(self):
            """Update row by task."""
            if not self.task or self.updating:
                return
            self.updating = True

            def _stylize(item):
                """Set item style. """

                item.setBackground(self.brushes[self.task.state][0])
                item.setForeground(self.brushes[self.task.state][1])

            LOGGER.debug('update row: %s', self.task)
            assert all(isinstance(i, QtWidgets.QTableWidgetItem) for i in self)

            self[0].setText(self.task.filename)
            self[0].setCheckState(QtCore.Qt.CheckState(
                2 if self.task.is_enabled else 0))
            self[0].setFlags(self.flags[self.task.state][0])

            self[1].setText(str(self.task.priority))
            self[1].setFlags(self.flags[self.task.state][1])

            _stylize(self[0])
            _stylize(self[1])

            self.updating = False

    def __init__(self, widget, parent):
        super(TaskTable, self).__init__(parent)
        self._rows = []
        self.widget = widget
        assert isinstance(parent, MainWindow)
        self.parent = parent
        self.queue = self.parent.queue
        assert isinstance(self.queue, render.Queue)

        self.widget.setColumnWidth(0, 350)

        # self.widget.itemDoubleClicked.connect(self.open_file)
        self.parent.toolButtonCheckAll.clicked.connect(self.check_all)
        self.parent.toolButtonReverseCheck.clicked.connect(self.reverse_check)
        self.parent.toolButtonRemove.clicked.connect(self.remove_selected)
        self.widget.itemSelectionChanged.connect(self.on_selection_changed)

        # Timer for widget update
        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(self.update_queue)
        _timer.start(1000)

        self.widget.cellChanged.connect(self.on_cell_changed)
        self.queue_changed.connect(self.on_queue_changed)

    def __getitem__(self, index):
        return self._rows[index]

    def __delitem__(self, index):
        del self._rows[index]

    def __len__(self):
        return len(self._rows)

    def append(self, row):
        """Add row to last.  """
        assert isinstance(row, self.Row)
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
            for _ in range(change):
                self.append(self.Row())
        elif change < 0:
            self.widget.setRowCount(number)
            del self[number:]
        if change:
            self.queue_changed.emit()

    def update_queue(self):
        """Update queue to match files.  """
        # Disable.
        for row in self:
            if row.task.is_enabled and not os.path.exists(row.task.filename):
                LOGGER.debug('%s not existed in %s anymore.',
                             row.task.filename, os.getcwd())
                row.task.is_enabled = False
                row.update()

        # Add.
        render.FILES.update()
        changed = False
        for i in render.FILES:
            if i not in self.queue:
                LOGGER.debug('Add task: %s', i)
                self.queue.put(i)
                changed = True

        if changed:
            self.update_widget()

    def update_widget(self):
        """Update table to match task queue.  """

        LOGGER.debug('Update task table')

        old = list(self.queue)
        self.queue.sort()
        if old != self.queue:
            self.queue_changed.emit()

        self.set_row_count(len(self.queue))
        for index, task in enumerate(self.queue):
            row = self[index]
            assert isinstance(row, self.Row)
            row.task = task
            row.update()

    @QtCore.Slot(int, int)
    def on_cell_changed(self, row, column):
        """Callback on cell changed.  """
        if self[row].updating:
            return

        item = self.widget.item(row, column)
        task = self.queue[row]

        if column == 0:
            task.is_enabled = bool(item.checkState())
            LOGGER.debug('Change enabled: %s', task)
            self[row].update()
            self.queue_changed.emit()
        elif column == 1:
            try:
                text = item.text()
                task.priority = int(text)
                LOGGER.debug('Change priority: %s', task)
            except ValueError:
                LOGGER.warning('不能识别优先级 %s, 重置为', text)
                item.setText(unicode(task.priority))
            else:
                self.update_widget()

    def on_selection_changed(self):
        """Do work on selection changed.  """

        self.parent.toolButtonRemove.setEnabled(bool(self.current_selected()))

    def on_queue_changed(self):
        """Do work on queue changed.  """
        _old_files = render.FILES.old_version_files()
        _button = self.parent.pushButtonRemoveOldVersion
        _button.setEnabled(bool(_old_files))
        _button.setToolTip('备份后从目录中移除低版本文件\n{}'.format('\n'.join(_old_files)))

        _enabled = any(i for i in self.queue if i.state == 'disabled')
        self.parent.toolButtonCheckAll.setEnabled(_enabled)

    @property
    def checked_files(self):
        """Return files checked in listwidget.  """
        return (i.text() for i in self.items() if i.checkState())

    def items(self):
        """Item in list widget -> list."""

        widget = self.widget
        return list(widget.item(i, 0) for i in xrange(widget.rowCount()))

    def check_all(self):
        """Check all item.  """

        changed = False
        for row in self:
            task = row.task
            assert isinstance(task, render.Task)
            if task.state == 'disabled':
                task.is_enabled = True
                row.update()
                changed = True
        if changed:
            self.queue_changed.emit()

    def reverse_check(self):
        """Reverse checkstate for every item.  """

        changed = False
        for row in self:
            task = row.task
            assert isinstance(task, render.Task)
            if task.state in ('waiting', 'disabled'):
                task.is_enabled = not task.is_enabled
                row.update()
                changed = True
        if changed:
            self.queue_changed.emit()

    def current_selected(self):
        """Current selected tasks.  """

        rows = set()
        _ = [rows.add(i.row()) for i in self.widget.selectedItems()]
        ret = [self[i].task for i in rows]
        LOGGER.debug('Current selected: %s',
                     ''.join(['\n{}'.format(i) for i in ret]) or '<None>')
        return ret

    def remove_selected(self):
        """Select all item in list widget.  """

        tasks = self.current_selected()

        for i in tasks:
            self.queue.remove(i)
            render.Files.remove(i.filename)
            LOGGER.debug('Remove task: %s', i)

        if tasks:
            self.update_widget()


def hiber():
    """Hibernate this computer.  """

    LOGGER.info('休眠')
    proc = subprocess.Popen('SHUTDOWN /H', stderr=subprocess.PIPE)
    stderr = get_unicode(proc.communicate()[1])
    LOGGER.error(stderr)
    if '没有启用休眠' in stderr:
        LOGGER.info('没有启用休眠, 转为使用关机')
        shutdown()


def shutdown():
    """Shutdown this computer.  """

    LOGGER.info('关机')
    subprocess.call('SHUTDOWN /S')


def call_from_nuke():
    """For nuke menu call.  """
    CONFIG['NUKE'] = sys.executable

    if sys.platform == 'win32':
        # Try use built executable
        try:
            dist_dir = os.path.join(os.path.dirname(__file__), 'dist')
            exe_path = sorted([os.path.join(dist_dir, i)
                               for i in os.listdir(dist_dir)
                               if i.endswith('.exe') and i.startswith('batchrender')],
                              key=os.path.getmtime, reverse=True)[0]
            webbrowser.open(exe_path)
            return
        except (IndexError, OSError):
            LOGGER.debug('Executable not found in %s', dist_dir)

    _file = __file__.rstrip('c')
    render_dir = CONFIG['DIR']
    if not os.path.exists(render_dir):
        render_dir = os.path.expanduser('~/batchrender')
        if not os.path.exists(render_dir):
            os.mkdir(render_dir)
        CONFIG['DIR'] = render_dir
    args = [sys.executable, '--tg', _file]
    if sys.platform == 'win32':
        args = [os.path.join(os.path.dirname(
            sys.executable), 'python.exe'), _file]
        kwargs = {'creationflags': subprocess.CREATE_NEW_CONSOLE}
    else:
        args = '"{0[0]}" {0[1]} "{0[2]}"'.format(args)
        kwargs = {'shell': True, 'executable': 'bash'}
    subprocess.Popen(args,
                     cwd=render_dir,
                     **kwargs)


def main():
    """Run this script standalone."""
    atexit.register(lambda: LOGGER.debug('Python exit.'))
    try:
        working_dir = CONFIG['DIR']
        os.chdir(working_dir)
        LOGGER.debug('Change dir: %s', os.getcwd())
    except OSError:
        LOGGER.warning('Can not change dir to: %s', working_dir)
    app = Application.instance()
    if not app:
        app = Application(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())
    LOGGER.debug('Exit')


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except:
        LOGGER.error('Uncaught exception.', exc_info=True)
        raise
