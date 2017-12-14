# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

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
from Qt.QtCore import Signal, Slot, QTimer, Qt, QEvent, QUrl
from Qt.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox,\
    QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox,\
    QStyle, QInputDialog
from tasktable import TaskTable

import render
from config import CONFIG, stylize
from path import get_unicode
from __version__ import __version__
from actions import hiber, shutdown


LOGGER = logging.getLogger()
DEFAULT_DIR = os.path.expanduser('~/.nuke/batchrender')


if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)

if sys.getdefaultencoding() != 'UTF-8':
    reload(sys)
    sys.setdefaultencoding('UTF-8')


class MainWindow(QMainWindow):
    """Main GUI window.  """

    _auto_start = False
    file_dropped = Signal(list)

    def __init__(self, parent=None):
        def _edits(edits_key):
            for edit, key in edits_key.iteritems():
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

        # ui
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../mainwindow.ui')))
        self.setCentralWidget(self._ui)
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.frameLowPriority.setVisible(CONFIG['LOW_PRIORITY'])
        self.labelVersion.setText('v{}'.format(__version__))
        _icon()
        self.resize(500, 700)

        # Connect edit to config
        edits_key = {
            self.lineEditDir: 'DIR',
            self.checkBoxProxy: 'PROXY',
            self.checkBoxPriority: 'LOW_PRIORITY',
            self.checkBoxContinue: 'CONTINUE',
            self.comboBoxAfterFinish: 'AFTER_FINISH',
            self.doubleSpinBoxMemory: 'MEMORY_LIMIT',
            self.spinBoxTimeOut: 'TIME_OUT'
        }
        _edits(edits_key)

        # Initiate render object.
        self.queue = render.Queue()
        self.on_queue_changed()
        self.slave = render.Slave()

        # Custom ui with render object.
        self.task_table = TaskTable(self.tableWidget, self)
        self.Title(self)

        # Signals.
        self.lineEditDir.textChanged.connect(self.check_dir)
        self.comboBoxAfterFinish.currentIndexChanged.connect(
            self.on_after_render_changed)

        self.toolButtonAskDir.clicked.connect(self.ask_dir)
        self.toolButtonOpenDir.clicked.connect(
            lambda: webbrowser.open(CONFIG['DIR']))
        self.toolButtonOpenLog.clicked.connect(
            lambda: webbrowser.open(CONFIG.log_path))

        self.pushButtonStart.clicked.connect(self.on_start_button_clicked)
        self.pushButtonStop.clicked.connect(self.on_stop_button_clicked)

        self.textBrowser.anchorClicked.connect(open_path)

        self.queue.changed.connect(self.on_queue_changed)
        self.queue.progressed.connect(self.progressBar.setValue)
        self.queue.stdout.connect(self.textBrowser.append)
        self.queue.stderr.connect(self.textBrowser.append)

        self.slave.stopped.connect(self.on_render_stopped)
        self.slave.finished.connect(self.on_render_finished)
        self.slave.time_out.connect(self.on_slave_time_out)

        self.progressBar.valueChanged.connect(self.append_timestamp)

        # File drop
        self.setAcceptDrops(True)
        self.file_dropped.connect(self.on_file_dropped)

        # Key pressed
        self.tableWidget.installEventFilter(self)

    def __getattr__(self, name):
        return getattr(self._ui, name)

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

            self.parent.queue.changed.connect(self.update_prefix)
            self.parent.progressBar.valueChanged.connect(self.update_prefix)

            self.parent.slave.started.connect(self._timer.start)
            self.parent.slave.finished.connect(self._timer.stop)

            self.update()

        def update_prefix(self):
            """Update title prefix with progress.  """

            prefix = ''
            queue_length = len(list(self.parent.queue.enabled_tasks()))

            if queue_length:
                prefix = '[{}]{}'.format(queue_length, prefix)
            if self.parent.slave.rendering:
                prefix = '{}%{}'.format(
                    self.parent.progressBar.value(), prefix)

            if prefix != self.prefix:
                self.prefix = prefix
                self.update()

        def update(self):
            """Update title, rotate when rendering.  """

            slave = self.parent.slave
            if slave.rendering:
                task = slave.task
                assert isinstance(task, render.Task)
                title = task.filename.partition('.nk')[0] or self.default_title
                self.title_index += 1
                index = self.title_index % len(title)
            else:
                title = self.default_title
                self.title_index = 0
                index = 0

            title = '{}{} {}'.format(
                self.prefix, title[index:], title[:index])

            self.parent.setWindowTitle(title)

    def append_timestamp(self):
        """Create timestamp in text browser.  """

        self.textBrowser.append(stylize(time.strftime('[%x %X]'), 'info'))

    def autostart(self):
        """Auto start rendering depend on setting.  """

        if (self._auto_start
                and not self.slave.rendering
                and self.queue):
            self._auto_start = False
            self.pushButtonStart.clicked.emit()
            LOGGER.info('发现新任务, 自动开始渲染')

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

    # Slots.

    @Slot(list)
    def on_file_dropped(self, files):
        files = [i for i in files if i.endswith('.nk')]
        if files:
            _ = [self.queue.put(i) for i in files]
            LOGGER.debug('Add %s', files)
        else:
            QMessageBox.warning(self, '不支持的格式', '目前只支持nk文件')

    @Slot()
    def on_queue_changed(self):

        # Set button: start button.
        if self.queue:
            self.pushButtonStart.setEnabled(True)
        else:
            self.pushButtonStart.setEnabled(False)

        # Set button: Remove old version.
        render.FILES.update()
        old_files = render.FILES.old_version_files()
        button = self.pushButtonRemoveOldVersion
        button.setEnabled(bool(old_files))
        button.setToolTip('备份后从目录中移除低版本文件\n{}'.format(
            '\n'.join(old_files) or '<无>'))

        # Set button: checkall.
        _enabled = any(i for i in self.queue if i.state & render.DISABLED)
        self.toolButtonCheckAll.setEnabled(_enabled)

        # Set button: start, stop.
        remains = self.queue.remains
        text = ('[{}]'.format(render.timef(int(remains)))
                if remains else '')
        self.pushButtonStart.setText('启动' + text)
        self.pushButtonStop.setText('停止' + text)

        self.autostart()

    @Slot()
    def on_after_render_changed(self):
        edit = self.comboBoxAfterFinish
        text = edit.currentText()
        LOGGER.debug('After render change to %s', text)

        def _reset():
            edit.setCurrentIndex(0)

        def _deadline():
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

        def _run_command():
            cmd, confirm = QInputDialog.getText(
                self, '执行命令', '命令内容', text=CONFIG['AFTER_FINISH_CMD'])
            if confirm and cmd:
                CONFIG['AFTER_FINISH_CMD'] = cmd
                LOGGER.info('渲染后执行命令: %s', cmd)
                edit.setToolTip(cmd)
            else:
                _reset()

        def _run_exe():
            path = QFileDialog.getOpenFileName(
                self, '渲染完成后运行...', dir=CONFIG['AFTER_FINISH_PROGRAM'])[0]
            if path:
                CONFIG['AFTER_FINISH_PROGRAM'] = path
                LOGGER.info('渲染后运行程序: %s', path)
                edit.setToolTip(path)
            else:
                _reset()

        if text != '等待新任务':
            self._auto_start = False

        if text == 'Deadline':
            _deadline()
        elif text == '执行命令':
            _run_command()
        elif text == '运行程序':
            _run_exe()
        else:
            edit.setToolTip('')

        if text in ('关机', '休眠', 'Deadline'):
            self.checkBoxPriority.setCheckState(Qt.Unchecked)
        else:
            self.checkBoxPriority.setCheckState(Qt.Checked)

    @Slot()
    def on_slave_time_out(self):
        """Wiil be excuted when frame take too long.  """

        if CONFIG['LOW_PRIORITY']:
            msg = '渲染超时, 关闭低优先级。'
            LOGGER.info(msg)
            self.textBrowser.append(stylize(msg, 'error'))
            self.checkBoxPriority.setCheckState(Qt.Unchecked)

    @Slot()
    def on_start_button_clicked(self):
        self.tabWidget.setCurrentIndex(1)

        start_error_handler()
        self.slave.start(self.queue)

    @Slot()
    def on_stop_button_clicked(self):
        self.comboBoxAfterFinish.setCurrentIndex(0)

        self.slave.stop()

    @Slot()
    def on_render_stopped(self):
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.pushButtonStart.show()
        self.tabWidget.setCurrentIndex(0)
        QApplication.alert(self)

    @Slot()
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

        actions.get(after_finish,
                    lambda: LOGGER.error('Not found match action for %s', after_finish))()

    # Events.
    def dragEnterEvent(self, event):
        # LOGGER.debug('Drag into %s', self)
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        widget = self.tableWidget
        if widget.isVisible() \
                and widget.geometry().contains(widget.mapFrom(self, event.pos()) + widget.pos()):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        event.accept()
        links = []
        for url in event.mimeData().urls():
            links.append(get_unicode(url.toLocalFile()))
        LOGGER.debug('Dropped files: %s', ', '.join(links))
        self.file_dropped.emit(links)

    def closeEvent(self, event):
        if self.slave.rendering:
            confirm = QMessageBox.question(
                self,
                '正在渲染中',
                "停止渲染并退出?",
                QMessageBox.Yes |
                QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.slave.stop()

                def _on_stopped():
                    QApplication.exit()
                    LOGGER.info('渲染途中退出')
                self.slave.stopped.connect(_on_stopped)
            else:
                event.ignore()
        else:
            QApplication.exit()
            LOGGER.info('退出')

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
