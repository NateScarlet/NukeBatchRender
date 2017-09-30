#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""
# TODO: title change when rendering
# TODO: file can change order manually
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

import render
import singleton
from config import Config
from path import get_unicode
from log import MultiProcessingHandler

if __name__ == '__main__':
    __SINGLETON = singleton.SingleInstance()

try:
    from Qt import QtCompat, QtCore, QtWidgets
    from Qt.QtWidgets import QApplication, QFileDialog, QMainWindow
except:
    raise

__version__ = '0.8.9'

LOGGER = logging.getLogger()


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
    path = Config().log_path
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


_set_logger()

if sys.getdefaultencoding() != 'UTF-8':
    reload(sys)
    sys.setdefaultencoding('UTF-8')


class MainWindow(QMainWindow):
    """Main GUI window.  """
    render_pool = None

    def __init__(self, parent=None):
        def _actions():
            self.actionRender.triggered.connect(self.render)
            self.actionDir.triggered.connect(self.ask_dir)
            self.actionStop.triggered.connect(self.stop_button_clicked)
            self.actionOpenDir.triggered.connect(self.open_dir)
            self.actionRemoveOldVersion.triggered.connect(
                self.remove_old_version)

        def _edits():
            for edit, key in self.edits_key.iteritems():
                if isinstance(edit, QtWidgets.QLineEdit):
                    edit.textChanged.connect(
                        lambda text, k=key: self._config.__setitem__(k, text))
                elif isinstance(edit, QtWidgets.QCheckBox):
                    edit.stateChanged.connect(
                        lambda state, k=key: self._config.__setitem__(k, state))
                elif isinstance(edit, QtWidgets.QComboBox):
                    edit.currentIndexChanged.connect(
                        lambda index, ex=edit, k=key:
                        self._config.__setitem__(k, ex.itemText(index)))
                else:
                    LOGGER.debug('待处理的控件: %s %s', type(edit), edit)

        def _icon():
            _stdicon = self.style().standardIcon

            _icon = _stdicon(QtWidgets.QStyle.SP_MediaPlay)
            self.setWindowIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DirOpenIcon)
            self.toolButtonOpenDir.setIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DialogOpenButton)
            self.toolButtonDir.setIcon(_icon)

        QMainWindow.__init__(self, parent)
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../batchrender.ui')))
        self.setCentralWidget(self._ui)
        self.task_table = TaskTable(self.tableWidget)
        self.resize(600, 500)
        self.setWindowTitle('Nuke批渲染')

        self._config = Config()
        self._proc = None
        self.rendering = False

        self.edits_key = {
            self.dirEdit: 'DIR',
            self.proxyCheck: 'PROXY',
            self.priorityCheck: 'LOW_PRIORITY',
            self.continueCheck: 'CONTINUE',
            self.hiberCheck: 'HIBER',
        }
        self.update()
        self._start_update()
        self.versionLabel.setText('v{}'.format(__version__))

        _actions()
        _edits()
        _icon()
        render.Files().unlock_all()

    def __getattr__(self, name):
        return getattr(self._ui, name)

    def __del__(self):
        if self.render_pool:
            self.render_pool.terminate()

    @property
    def is_rendering(self):
        """If render runing.  """
        return self.render_pool and self.render_pool.is_alive()

    def open_dir(self):
        """Open dir in explorer.  """
        webbrowser.open(self._config['DIR'])

    def open_log(self):
        """Open log in explorer.  """
        # TODO: open log
        pass

    def _start_update(self):
        """Start a thread for update.  """

        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(self.update)
        _timer.start(1000)

    def update(self):
        """Update UI content.  """

        rendering = self.render_pool and self.render_pool.is_alive()
        if not rendering and self.rendering:
            self.on_stop_callback()
        self.rendering = rendering
        _files = render.Files()

        def _button_enabled():
            if rendering:
                self.renderButton.setEnabled(False)
                self.stopButton.setEnabled(True)
                self.tableWidget.setStyleSheet(
                    'color:white;background-color:rgb(12%, 16%, 18%);')
                self.pushButtonRemoveOldVersion.setEnabled(False)
            else:
                if os.path.isdir(self._config['DIR']) and _files:
                    self.renderButton.setEnabled(True)
                else:
                    self.renderButton.setEnabled(False)
                self.stopButton.setEnabled(False)
                self.tableWidget.setStyleSheet('')
                self.pushButtonRemoveOldVersion.setEnabled(True)

        def _edits():
            for qt_edit, k in self.edits_key.items():
                try:
                    if isinstance(qt_edit, QtWidgets.QLineEdit):
                        qt_edit.setText(self._config[k])
                    if isinstance(qt_edit, QtWidgets.QCheckBox):
                        qt_edit.setCheckState(
                            QtCore.Qt.CheckState(self._config[k]))
                except KeyError as ex:
                    LOGGER.debug(ex)

        if not rendering and self.checkBoxAutoStart.isChecked() \
                and _files and not _files.all_locked:
            self.render()
        _edits()
        _button_enabled()

    def on_stop_callback(self):
        """Do work when rendering stop.  """

        QApplication.alert(self)
        LOGGER.info('渲染结束')
        self.statusbar.showMessage('')
        if self.hiberCheck.isChecked():
            LOGGER.info('休眠')
            self.hiberCheck.setCheckState(QtCore.Qt.CheckState.Unchecked)
            hiber()

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        dialog = QFileDialog()
        dir_ = dialog.getExistingDirectory(
            dir=os.path.dirname(self._config['DIR']))
        if dir_:
            try:
                dir_.encode('ascii')
            except UnicodeEncodeError:
                self.statusbar.showMessage('Nuke只支持英文路径', 10000)
            else:
                self._config['DIR'] = dir_

    def render(self):
        """Start rendering from UI.  """
        _file = os.path.abspath(os.path.join(__file__, '../error_handler.exe'))
        webbrowser.open(_file)
        self.render_pool = render.Pool(self.task_table.queue)
        self.render_pool.start()
        self.statusbar.showMessage('渲染中')

    @staticmethod
    def remove_old_version():
        """Remove old version nk files from UI.  """

        render.Files().remove_old_version()

    def stop_button_clicked(self):
        """Stop rendering from UI."""

        self.hiberCheck.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.checkBoxAutoStart.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.render_pool.terminate()

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
                sys.exit()
            else:
                event.ignore()
        else:
            sys.exit()


class TaskTable(object):
    """Table widget.  """

    def __init__(self, widget):
        self.widget = widget
        self.parent = self.widget.parent()
        self.queue = render.TaskQueue()
        self._lock = multiprocessing.Lock()
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
        self.widget.setColumnWidth(0, 300)
        self.widget.showEvent = self.showEvent
        self.widget.hideEvent = self.hideEvent
        self._start_update()

    def __del__(self):
        self._lock.acquire()

    @property
    def directory(self):
        """Current working dir.  """
        return self.parent.directory

    def showEvent(self, event):
        def _run():
            LOGGER.debug('TableWidget update start')
            lock = self._lock
            while lock.acquire(False):
                try:
                    if self.widget.isVisible():
                        self.update()
                except RuntimeError:
                    pass
                time.sleep(1)
                lock.release()
        self.update()
        thread = multiprocessing.dummy.Process(
            name='TaskTableUpdate', target=_run)
        thread.daemon = True
        thread.start()
        event.accept()

    def hideEvent(self, event):
        event.accept()
        self._lock.acquire()
        self._lock.release()

    def update(self):
        """Update info.  """
        widget = self.widget
        files = render.Files()
        files.update()

        # Remove.
        for item in self.items():
            if not item:
                continue
            text = item.text()
            if text not in files:
                widget.removeRow(item.row())

            elif item.checkState() \
                    and isinstance(self.parent.get_dest(text, refresh=True), Exception):
                item.setCheckState(QtCore.Qt.Unchecked)

        # Add.
        for i in files:
            try:
                item = self.widget.findItems(
                    i, QtCore.Qt.MatchExactly)[0]
            except IndexError:
                LOGGER.debug('Add task: %s', i)
                self.add_task(render.Task(i))

        # # Count
        # self.parent.labelCount.setText(
        #     '{}/{}/{}'.format(len(list(self.checked_files)), len(local_files), len(all_files)))

    def add_task(self, task):
        """Add task to the task table and queue.  """
        row = self.widget.rowCount()
        self.widget.insertRow(row)
        LOGGER.debug('Insert row: %s', row)
        _item = QtWidgets.QTableWidgetItem(task.file)
        _item.setCheckState(QtCore.Qt.Unchecked)
        self.widget.setItem(row, 0, _item)
        _item = QtWidgets.QTableWidgetItem('0')
        self.widget.setItem(row, 1, _item)
        self.queue.put(task)

    def _start_update(self):
        def _run():
            LOGGER.debug('TableWidget update start')
            lock = self._lock
            while lock.acquire(False):
                try:
                    if self.widget.isVisible():
                        self.update()
                except RuntimeError:
                    pass
                time.sleep(1)
                lock.release()
        thread = multiprocessing.dummy.Process(
            name='TaskTableUpdate', target=_run)
        thread.daemon = True
        thread.start()

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

    proc = subprocess.Popen('SHUTDOWN /H', stderr=subprocess.PIPE)
    stderr = get_unicode(proc.communicate()[1])
    LOGGER.error(stderr)
    if '没有启用休眠' in stderr:
        LOGGER.info('没有启用休眠, 转为使用关机')
        subprocess.call('SHUTDOWN /S')


def call_from_nuke():
    """For nuke menu call.  """

    Config()['NUKE'] = sys.executable
    _file = __file__.rstrip('c')
    render_dir = Config()['DIR']
    if not os.path.exists(render_dir):
        render_dir = os.path.expanduser('~/batchrender')
        if not os.path.exists(render_dir):
            os.mkdir(render_dir)
        Config()['DIR'] = render_dir
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
        working_dir = Config()['DIR']
        os.chdir(working_dir)
    except OSError:
        LOGGER.warning('Can not change dir to: %s', working_dir)
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())
    LOGGER.debug('Exit')


if __name__ == '__main__':
    main()
