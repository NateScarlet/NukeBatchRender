#! /usr/bin/env python2
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
import time
from functools import wraps


from Qt import QtCompat
from Qt.QtCore import Signal, Slot, QTimer, Qt, QEvent, QPoint, QUrl
from Qt.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox,\
    QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox,\
    QStyle, QInputDialog
from tasktable import TaskTable

import render
from config import CONFIG, stylize
from log import MultiProcessingHandler
from path import get_unicode
from __version__ import __version__
from actions import hiber, shutdown


LOGGER = logging.getLogger()
DEFAULT_DIR = os.path.expanduser('~/.nuke/batchrender')


def _set_logger():
    logger = logging.getLogger()
    logger.propagate = False

    # Loglevel
    loglevel = os.getenv('LOGLEVEL', logging.INFO)
    try:
        logger.setLevel(int(loglevel))
    except TypeError:
        logger.warning(
            'Can not recognize env:LOGLEVEL %s, expect a int', loglevel)

    # Stream handler
    _handler = MultiProcessingHandler(logging.StreamHandler)
    if logger.getEffectiveLevel() == logging.DEBUG:
        _formatter = logging.Formatter(
            '%(levelname)-6s[%(asctime)s]:%(filename)s:'
            '%(lineno)d:%(funcName)s: %(message)s', '%H:%M:%S')
    else:
        _formatter = logging.Formatter(
            '%(levelname)-6s[%(asctime)s]:'
            '%(name)s: %(message)s', '%H:%M:%S')

    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.debug('Added stream handler.  ')

    # File handler
    path = CONFIG.log_path
    path_dir = os.path.dirname(path)
    try:
        os.makedirs(path_dir)
    except OSError:
        pass
    _handler = MultiProcessingHandler(
        logging.handlers.RotatingFileHandler,
        args=(path,), kwargs={'backupCount': 5})
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]:%(name)s: %(message)s', '%x %X')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
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


class MainWindow(QMainWindow):
    """Main GUI window.  """
    render_pool = None
    _auto_start = False
    restarting = False
    render_started = Signal()
    render_finished = Signal()
    file_dropped = Signal(list)

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

            self._timer = QTimer()
            self._timer.setInterval(300)
            self._timer.timeout.connect(self.update)
            setattr(self.parent, '_title', self)

            self.parent.render_finished.connect(self.update_prefix)
            self.parent.queue.changed.connect(self.update_prefix)
            self.parent.progressBar.valueChanged.connect(self.update_prefix)

            self.parent.render_started.connect(self._timer.start)
            self.parent.render_finished.connect(self._timer.stop)

            self.update()

        def update_prefix(self):
            """Update title prefix with progress.  """
            prefix = ''
            queue_length = len([
                i for i in self.parent.queue if not i.state])

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

            if self.parent.is_rendering and self.parent.render_pool.current_task:
                title = self.parent.render_pool.current_task.filename.partition('.nk')[
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

            self.textBrowser.anchorClicked.connect(open_path)

            self.render_started.connect(lambda: self.progressBar.setValue(0))
            self.render_finished.connect(self.on_render_finished)

            self.queue.changed.connect(self.on_queue_changed)

            self.progressBar.valueChanged.connect(self.append_timestamp)

        def _edits():
            for edit, key in self.edits_key.iteritems():
                if isinstance(edit, QLineEdit):
                    edit.setText(CONFIG.get(key, ''))
                    edit.editingFinished.connect(
                        lambda edit=edit, k=key: CONFIG.__setitem__(k, edit.text()))
                elif isinstance(edit, QCheckBox):
                    edit.setCheckState(
                        Qt.CheckState(CONFIG.get(key, 0)))
                    edit.stateChanged.connect(
                        lambda state, k=key: CONFIG.__setitem__(k, state))
                elif isinstance(edit, QComboBox):
                    edit.setCurrentIndex(CONFIG.get(key, 0))
                    edit.currentIndexChanged.connect(
                        lambda index, k=key: CONFIG.__setitem__(k, index))
                elif isinstance(edit, QSpinBox):
                    edit.setValue(CONFIG.get(key, 0))
                    edit.valueChanged.connect(
                        lambda value, k=key: CONFIG.__setitem__(k, value))
                elif isinstance(edit, QDoubleSpinBox):
                    edit.setValue(CONFIG.get(key, 0))
                    edit.valueChanged.connect(
                        lambda value, k=key: CONFIG.__setitem__(k, value))
                else:
                    LOGGER.debug('待处理的控件: %s %s', type(edit), edit)

        def _icon():
            _stdicon = self.style().standardIcon

            _icon = _stdicon(QStyle.SP_MediaPlay)
            self.setWindowIcon(_icon)

            _icon = _stdicon(QStyle.SP_DirOpenIcon)
            self.toolButtonOpenDir.setIcon(_icon)

            _icon = _stdicon(QStyle.SP_DialogOpenButton)
            self.toolButtonAskDir.setIcon(_icon)

        super(MainWindow, self).__init__(parent)
        self.queue = render.Queue()
        self.queue.clock.remains_changed.connect(self.on_remains_changed)
        self.queue.clock.time_out.connect(self.on_task_time_out)

        # ui
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../mainwindow.ui')))
        self.setCentralWidget(self._ui)
        self.task_table = TaskTable(self.tableWidget, self)
        self.Title(self)
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.frameLowPriority.setVisible(CONFIG['LOW_PRIORITY'])
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
            self.doubleSpinBoxMemory: 'MEMORY_LIMIT',
            self.spinBoxTimeOut: 'TIME_OUT'
        }
        _edits()

        self.new_render_pool()

        _signals()

        # File drop
        self.setAcceptDrops(True)
        self.file_dropped.connect(self.on_file_dropped)

        # Key pressed
        self.tableWidget.installEventFilter(self)

    def append_timestamp(self):
        """Create timestamp in text browser.  """

        self.textBrowser.append(stylize(time.strftime('[%x %X]'), 'info'))

    def eventFilter(self, widget, event):
        """Qt widget event filter.  """

        if (event.type() == QEvent.KeyPress and
                widget is self.tableWidget):
            key = event.key()

            if key == Qt.Key_Return:
                selected_task = self.task_table.current_selected()
                if len(selected_task) <= 1:
                    return True
                priority, confirm = QInputDialog.getInt(
                    self, '为所选设置优先级', '优先级')
                if confirm:
                    for task in selected_task:
                        task.priority = priority
                        self.task_table[task].update()
                    self.task_table.update_queue()
            return True
        return super(MainWindow, self).eventFilter(widget, event)

    def absolute_pos(self, widget):
        """Return absolute postion for child @widget.  """

        ret = QPoint(0, 0)
        widget = widget.parent()
        while widget and widget is not self:
            ret += widget.pos()
            widget = widget.parent()

        return ret

    def is_pos_in_widget(self, pos, widget):
        """Return if @pos in @widget geometry.  """
        if not widget.isVisible():
            return False
        return widget.geometry().contains(pos - self.absolute_pos(widget))

    @Slot(list)
    def on_file_dropped(self, files):
        files = [i for i in files if i.endswith('.nk')]
        if files:
            _ = [self.queue.put(i) for i in files]
            LOGGER.debug('Add %s', files)
        else:
            QMessageBox.warning(self, '不支持的格式', '目前只支持nk文件')

    def dragEnterEvent(self, event):
        LOGGER.debug('Drag into %s', self)
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):

        if self.is_pos_in_widget(event.pos(), self.tableWidget):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.is_pos_in_widget(event.pos(), self.tableWidget):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(get_unicode(url.toLocalFile()))
            LOGGER.debug('Dropped files: %s', ', '.join(links))
            self.file_dropped.emit(links)
        else:
            event.ignore()

    def __getattr__(self, name):
        return getattr(self._ui, name)

    @property
    def is_rendering(self):
        """If render runing.  """
        return self.render_pool and self.render_pool.isRunning()

    def on_render_finished(self):

        def reset_after_render(func):
            """(Decorator)Reset after render choice before run @func  ."""

            @wraps(func)
            def _func(*args, **kwargs):
                self.comboBoxAfterFinish.setCurrentIndex(0)
                return func(*args, **kwargs)
            return _func

        after_finish = self.comboBoxAfterFinish.currentText()

        actions = {
            '等待新任务': lambda: setattr(self, '_auto_start', True),
            '休眠': reset_after_render(hiber),
            '关机': reset_after_render(shutdown),
            'Deadline': reset_after_render(lambda: webbrowser.open(CONFIG['DEADLINE'])),
            '执行命令': lambda: subprocess.Popen(CONFIG['AFTER_FINISH_CMD'], shell=True),
            '运行程序': lambda: webbrowser.open(CONFIG['AFTER_FINISH_PROGRAM']),
            '什么都不做': lambda: LOGGER.info('渲染完成后什么都不做')
        }

        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.pushButtonStart.show()
        self.tabWidget.setCurrentIndex(0)

        if not self.render_pool.stopping:
            QApplication.alert(self)
            actions.get(after_finish, lambda: LOGGER.error(
                'Not found match action for %s', after_finish))()

        self.new_render_pool()
        if self.restarting:
            self.restarting = False
            self.pushButtonStart.clicked.emit()

    def autostart(self):
        """Auto start rendering depend on setting.  """

        if self._auto_start and not self.render_pool.isRunning():
            self._auto_start = False
            self.pushButtonStart.clicked.emit()
            LOGGER.info('发现新任务, 自动开始渲染')

    def on_queue_changed(self):

        # Set button: start button.
        if self.task_table.queue:
            self.pushButtonStart.setEnabled(True)
        else:
            self.pushButtonStart.setEnabled(False)

        # Set button: emove old version.
        render.FILES.update()
        old_files = render.FILES.old_version_files()
        button = self.pushButtonRemoveOldVersion
        button.setEnabled(bool(old_files))
        button.setToolTip('备份后从目录中移除低版本文件\n{}'.format(
            '\n'.join(old_files) or '<无>'))

        # Set button: checkall.
        _enabled = any(i for i in self.queue if i.state & render.DISABLED)
        self.toolButtonCheckAll.setEnabled(_enabled)

        self.autostart()

    def on_after_render_changed(self):
        edit = self.comboBoxAfterFinish
        text = edit.currentText()
        LOGGER.debug('After render change to %s', text)

        def _reset():
            edit.setCurrentIndex(0)

        if text != '等待新任务':
            self._auto_start = False

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
            cmd, confirm = QInputDialog.getText(
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

        if text in ('关机', '休眠', 'Deadline'):
            self.checkBoxPriority.setCheckState(Qt.Unchecked)
        else:
            self.checkBoxPriority.setCheckState(Qt.Checked)

    def on_remains_changed(self, remains):
        text = '停止'
        if remains:
            text = '{}[{}]'.format(text, render.timef(int(remains)))
        self.pushButtonStop.setText(text)

        self.task_table[self.render_pool.current_task].update()

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        path = QFileDialog.getExistingDirectory(
            dir=os.path.dirname(CONFIG['DIR']))
        if path:
            if self.check_dir(path):
                CONFIG['DIR'] = path
                self.lineEditDir.setText(path)
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
            QMessageBox.information(
                self, path, 'Nuke只支持英文路径')
            return False
        return True

    def new_render_pool(self):
        """Switch to new render pool.  """

        LOGGER.debug('New render pool.')
        pool = render.Pool(self.task_table.queue)

        pool.stdout.connect(self.textBrowser.append)
        pool.stderr.connect(self.textBrowser.append)
        pool.progress.connect(self.progressBar.setValue)
        pool.queue_finished.connect(self.render_finished.emit)

        self.queue.clock.start_clock(pool)
        self.queue.clock.time_out_timer.stop()

        self.render_pool = pool

    def on_task_time_out(self):
        """Excute when frame take too long.  """

        if CONFIG['LOW_PRIORITY']:
            msg = '渲染超时, 关闭低优先级进行重试'
            LOGGER.info(msg)
            self.textBrowser.append(stylize(msg, 'error'))
            self.checkBoxPriority.setCheckState(Qt.Unchecked)
            self.render_pool.stop()
            self.restarting = True
        else:
            msg = '渲染超时'
            LOGGER.warning(msg)
            self.textBrowser.append(stylize(msg, 'error'))

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

    def closeEvent(self, event):
        """Override qt closeEvent."""

        if self.is_rendering:
            confirm = QMessageBox.question(
                self,
                '正在渲染中',
                "停止渲染并退出?",
                QMessageBox.Yes |
                QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.render_pool.stop()
                QApplication.exit()
                LOGGER.info('渲染途中退出')
            else:
                event.ignore()
        else:
            QApplication.exit()
            LOGGER.info('退出')


@Slot(QUrl)
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
        proc = subprocess.Popen(_file, close_fds=True)
        atexit.register(proc.terminate)
