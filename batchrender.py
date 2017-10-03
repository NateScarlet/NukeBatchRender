#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""
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
from config import Config
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
CONFIG = Config()

if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)


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
            self.parent.task_table.changed.connect(self.update_prefix)
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
                    0]
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

            self.task_table.changed.connect(self.on_task_table_changed)

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

        # render.Files().unlock_all()
        self.new_render_pool()

        _signals()

        # TODO
        self.toolButtonRemove.setEnabled(False)
        self.toolButtonSelectAll.setEnabled(False)
        self.toolButtonReverseSelection.setEnabled(False)

    def __getattr__(self, name):
        return getattr(self._ui, name)

    @property
    def is_rendering(self):
        """If render runing.  """
        return self.render_pool and self.render_pool.isRunning()

    def on_render_stopped(self):
        """Do work when rendering stop.  """

        after_render = self.comboBoxAfterFinish.currentText()
        actions = {
            '什么都不做': lambda: LOGGER.info('无渲染完成后任务'),
            '休眠': hiber,
            '关机': shutdown,
            'Deadline': lambda: webbrowser.open(CONFIG['DEADLINE']),
            '执行命令': lambda: subprocess.Popen(CONFIG['AFTER_RENDER_CMD'], shell=True),
            '运行程序': lambda: webbrowser.open(CONFIG['AFTER_RENDER_PROGRAM']),
        }

        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.pushButtonStart.show()
        self.pushButtonRemoveOldVersion.setEnabled(True)

        for task in self.queue:
            task.is_doing = False
        self.task_table.changed.emit()
        self.tabWidget.setCurrentIndex(0)

        Application.alert(self)

        self.new_render_pool()
        LOGGER.info('渲染结束')

        actions.get(after_render, lambda: LOGGER.error(
            'Not found match action for %s', after_render))()

    def on_task_table_changed(self):
        """Do work when task table changed.  """
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
                self, '选择Deadline Slave执行程序', dir=CONFIG['DEADLINE'], filter='deadlineslave.exe;;*.*', selectedFilter='deadlineslave.exe')[0]
            if path:
                CONFIG['DEADLINE'] = path
                LOGGER.info('Deadline 路径改为: %s', path)
                edit.setToolTip(path)
            else:
                _reset()
        elif text == '执行命令':
            cmd, confirm = QtWidgets.QInputDialog.getText(
                self, '执行命令', '命令内容', text=CONFIG['AFTER_RENDER_CMD'])
            if confirm and cmd:
                CONFIG['AFTER_RENDER_CMD'] = cmd
                LOGGER.info('渲染后执行命令: %s', cmd)
                edit.setToolTip(cmd)
            else:
                _reset()
        elif text == '运行程序':
            path = QFileDialog.getOpenFileName(
                self, '渲染完成后运行...', dir=CONFIG['AFTER_RENDER_PROGRAM'])[0]
            if path:
                CONFIG['AFTER_RENDER_PROGRAM'] = path
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
        self.render_pool = render.Pool(self.task_table.queue)
        self.render_pool.stdout.connect(self.textBrowser.append)
        self.render_pool.stderr.connect(self.textBrowser.append)
        self.render_pool.progress.connect(self.progressBar.setValue)
        self.render_pool.task_started.connect(self.task_table.changed)
        self.render_pool.task_finished.connect(self.task_table.changed)
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
    changed = QtCore.Signal()
    _updating = False

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

        def __init__(self, task=None):
            assert task is None or isinstance(task, render.Task)
            column = [QtWidgets.QTableWidgetItem() for _ in range(2)]
            list.__init__(self, column)

            self.task = task

            self.update()

        def update(self):
            """Update row by task."""
            if not self.task:
                return

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

    def __init__(self, widget, parent):
        super(TaskTable, self).__init__(parent)
        self._rows = []
        self.widget = widget
        assert isinstance(parent, MainWindow)
        self.parent = parent
        self.queue = self.parent.queue
        assert isinstance(self.queue, render.Queue)

        # self.widget.itemDoubleClicked.connect(self.open_file)
        # self.parent.actionSelectAll.triggered.connect(self.select_all)
        # self.parent.actionReverseSelection.triggered.connect(
        #     self.reverse_selection)
        self.widget.setColumnWidth(0, 350)

        # Timer for widget update
        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(self.update_queue)
        _timer.start(1000)

        self.widget.cellChanged.connect(self.on_cell_changed)
        self.changed.connect(self.update_widget)

    def __getitem__(self, index):
        return self._rows[index]

    def __delitem__(self, index):
        del self._rows[index]

    def __len__(self):
        return len(self._rows)

    def append(self, row):
        """Add row to last.  """
        assert isinstance(row, self.Row)
        index = len(self._rows)
        self._rows.append(row)
        for column, item in enumerate(row):
            self.widget.setItem(index, column, item)

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

    def update_queue(self):
        """Update queue to match files.  """
        files = render.Files()
        files.update()
        # Remove.
        for row in self:
            if not os.path.exists(row.task.filename):
                row.task.is_enabled = False
                self.changed.emit()

        # Add.
        for i in files:
            if i not in self.queue:
                LOGGER.debug('Add task: %s', i)
                self.queue.put(i)
                self.changed.emit()

    def update_widget(self):
        """Update table to match task queue.  """
        if self._updating:
            return

        self._updating = True

        self.queue.sort()
        self.set_row_count(len(self.queue))
        for index, task in enumerate(self.queue):
            row = self[index]
            assert isinstance(row, self.Row)
            row.task = task
            row.update()

        self._updating = False

    @QtCore.Slot(int, int)
    def on_cell_changed(self, row, column):
        """Callback on cell changed.  """
        if self._updating:
            return

        item = self.widget.item(row, column)
        task = self.queue[row]

        if column == 0:
            task.is_enabled = bool(item.checkState())
            LOGGER.debug('Change enabled: %s', task)
        elif column == 1:
            try:
                text = item.text()
                task.priority = int(text)
                LOGGER.debug('Change priority: %s', task)
            except ValueError:
                LOGGER.warning('不能识别优先级 %s', text)
                item.setText(unicode(task.priority))

        self._updating = True
        self[row].update()
        self.changed.emit()
        self._updating = False

    @property
    def checked_files(self):
        """Return files checked in listwidget.  """
        return (i.text() for i in self.items() if i.checkState())

    def items(self):
        """Item in list widget -> list."""

        widget = self.widget
        return list(widget.item(i, 0) for i in xrange(widget.rowCount()))

    # def select_all(self):
    #     """Select all item in list widget.  """
    #     for item in self.items():
    #         if item.text() not in self.uploaded_files:
    #             item.setCheckState(QtCore.Qt.Checked)

    # def reverse_selection(self):
    #     """Select all item in list widget.  """
    #     for item in self.items():
    #         if item.text() not in self.uploaded_files:
    #             if item.checkState():
    #                 item.setCheckState(QtCore.Qt.Unchecked)
    #             else:
    #                 item.setCheckState(QtCore.Qt.Checked)


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
    main()
