#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""
from __future__ import print_function, unicode_literals

import logging
import logging.handlers
import multiprocessing
import multiprocessing.dummy
import os
import subprocess
import sys
import time
import webbrowser
import atexit

import render
import singleton
from config import Config
from path import get_unicode
from log import MultiProcessingHandler

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
        '%(levelname)-6s[%(asctime)s]: %(name)s: %(message)s', '%H:%M:%S')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.debug('Added stream handler.  ')

    # File handler
    path = CONFIG.log_path
    _handler = MultiProcessingHandler(
        logging.handlers.RotatingFileHandler,
        args=(path,), kwargs={'backupCount': 5})
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]: %(name)s: %(message)s', '%x %X')
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

            self.parent.progressBar.valueChanged.connect(self.update_prefix)
            self.parent.render_stopped.connect(self.update_prefix)
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

        def _button_enabled():
            if self.is_rendering:
                # self.tableWidget.setStyleSheet(
                #     'color:white;background-color:rgb(12%, 16%, 18%);')
                self.pushButtonRemoveOldVersion.setEnabled(False)
            else:
                # self.tableWidget.setStyleSheet('')
                self.pushButtonRemoveOldVersion.setEnabled(True)
            if self.task_table.queue:
                self.pushButtonStart.setEnabled(True)
            else:
                self.pushButtonStart.setEnabled(False)
        QMainWindow.__init__(self, parent)

        # ui
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../batchrender.ui')))
        self.setCentralWidget(self._ui)
        self.task_table = TaskTable(self.tableWidget, self)
        self.Title(self)
        self.pushButtonStop.clicked.emit()
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

        _signals()

        render.Files().unlock_all()

        # Timer for button enabled
        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(_button_enabled)
        _timer.start(1000)

        # TODO
        self.toolButtonRemove.setEnabled(False)
        self.toolButtonSelectAll.setEnabled(False)
        self.toolButtonReverseSelection.setEnabled(False)

    def __getattr__(self, name):
        return getattr(self._ui, name)

    def __del__(self):
        if self.render_pool:
            self.render_pool.terminate()

    @property
    def is_rendering(self):
        """If render runing.  """
        return self.render_pool and self.render_pool.isRunning()

    def on_render_stopped(self):
        """Do work when rendering stop.  """
        after_render = self.comboBoxAfterFinish.currentText()
        actions = {
            '休眠': hiber,
            '关机': shutdown,
            '什么都不做': lambda: LOGGER.info('无渲染完成后任务')
        }

        Application.alert(self)
        self.pushButtonStop.clicked.emit()
        LOGGER.info('渲染结束')
        actions.get(after_render, lambda: LOGGER.error(
            'Not found match action for %s', after_render))()

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        dialog = QFileDialog(self)
        path = dialog.getExistingDirectory(
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

    def start_button_clicked(self):
        """Button clicked action.  """

        start_error_handler()
        LOGGER.debug('Task queue:\n %s', self.task_table.queue)
        self.render_pool = render.Pool(self.task_table.queue)
        self.render_pool.stdout.connect(self.textBrowser.append)
        self.render_pool.stderr.connect(self.textBrowser.append)
        self.render_pool.progress.connect(self.progressBar.setValue)
        self.render_pool.task_finished.connect(self.render_stopped.emit)
        self.render_pool.start()
        self.tabWidget.setCurrentIndex(1)
        self.render_started.emit()

    def stop_button_clicked(self):
        """Button clicked action.  """

        self.comboBoxAfterFinish.setCurrentIndex(0)
        if self.render_pool:
            self.render_pool.stop()
        self.tabWidget.setCurrentIndex(0)

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
                Application.exit()
            else:
                event.ignore()
        else:
            Application.exit()


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
    brushes = {
        'bg_doing': QtGui.QBrush(QtGui.QColor(30, 40, 45)),
        'fg_doing': QtGui.QBrush(QtGui.QColor(QtCore.Qt.white)),
        'bg_waiting': QtGui.QBrush(QtGui.QColor(QtCore.Qt.white)),
        'fg_waiting': QtGui.QBrush(QtGui.QColor(QtCore.Qt.black)),
    }

    def __init__(self, widget, parent):
        super(TaskTable, self).__init__(parent)
        self.widget = widget
        assert isinstance(parent, MainWindow)
        self.parent = parent or self.widget.parent()
        self.queue = render.TaskQueue()

        # self._brushes = {}
        # if HAS_NUKE:
        #     self._brushes['local'] = QtGui.QBrush(QtGui.QColor(200, 200, 200))
        #     self._brushes['uploaded'] = QtGui.QBrush(
        #         QtGui.QColor(100, 100, 100))
        # else:
        #     self._brushes['local'] = QtGui.QBrush(QtCore.Qt.black)
        #     self._brushes['uploaded'] = QtGui.QBrush(QtCore.Qt.gray)

        # self.widget.itemDoubleClicked.connect(self.open_file)
        # self.parent.actionSelectAll.triggered.connect(self.select_all)
        # self.parent.actionReverseSelection.triggered.connect(
        #     self.reverse_selection)
        self.widget.setColumnWidth(0, 350)

        # Timer for widget update
        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(self.update)
        _timer.start(1000)

        self.widget.cellChanged.connect(self.on_cell_changed)
        self._updating = False

    @property
    def directory(self):
        """Current working dir.  """
        return self.parent.directory

    def update(self):
        """Update queue to match files.  """
        # LOGGER.debug('TableWidget update')
        widget = self.widget
        files = render.Files()
        files.update()

        # Remove.
        for item in self.items():
            if not item:
                continue
            text = item.text()
            if self.parent.render_pool:
                if self.parent.render_pool.is_current_task(text):
                    item.setBackground(self.brushes['bg_doing'])
                    item.setForeground(self.brushes['fg_doing'])
                else:
                    item.setBackground(self.brushes['bg_waiting'])
                    item.setForeground(self.brushes['fg_waiting'])

            if text not in files:
                widget.removeRow(item.row())
                self.parent.update_title_prefix()

        # Add.
        found_new = False
        for i in files:
            try:
                item = self.widget.findItems(
                    i, QtCore.Qt.MatchExactly)[0]
            except IndexError:
                LOGGER.debug('Add task: %s', i)
                self.parent.update_title_prefix()
                self.queue.put(i)
                found_new = True

        if found_new:
            self.update_table()

    def update_table(self):
        """Update table to match task queue.  """
        self._updating = True

        self.queue.sort()
        row = len(self.queue)
        self.widget.setRowCount(row)
        LOGGER.debug('Update table row count: %s', row)
        for index, task in enumerate(self.queue):
            _item = QtWidgets.QTableWidgetItem(task.filename)
            _flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
            # TODO
            # _flags |= QtCore.Qt.ItemIsUserCheckable
            _item.setFlags(_flags)
            _item.setCheckState(QtCore.Qt.Checked)
            self.widget.setItem(index, 0, _item)
            _item = QtWidgets.QTableWidgetItem(str(task.priority))
            _item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsEditable)
            self.widget.setItem(index, 1, _item)

        self._updating = False

    @QtCore.Slot(int, int)
    def on_cell_changed(self, row, column):
        """Callback on cell changed.  """
        if self._updating:
            return

        item = self.widget.item(row, column)
        if column == 1:
            task = self.queue[row]
            try:
                text = item.text()
                task.priority = int(text)
            except ValueError:
                LOGGER.warning('不能识别优先级 %s', text)
                self._updating = True
                item.setText(unicode(task.priority))
                self._updating = False
            self.update_table()

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
    try:
        working_dir = CONFIG['DIR']
        os.chdir(working_dir)
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
