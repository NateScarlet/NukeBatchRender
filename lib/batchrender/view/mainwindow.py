# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import logging.handlers
import os
import subprocess
import sys
import time
import webbrowser
from functools import wraps

from Qt import QtCompat
from Qt.QtCore import Qt, QUrl, Signal, Slot
from Qt.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                          QFileDialog, QInputDialog, QLineEdit, QMainWindow,
                          QMessageBox, QSpinBox, QStyle)

from .. import render
from ..__about__ import __version__
from ..actions import hiber, shutdown
from ..codectools import get_unicode
from ..config import CONFIG, stylize
from ..control import Controller
from .title import Title

LOGGER = logging.getLogger()


if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)


def _link_edits_to_config(edits_key):
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


class MainWindow(QMainWindow):
    """Main GUI window.  """

    _auto_start = False
    file_dropped = Signal(list)

    def _setup_icon(self):
        _stdicon = self.style().standardIcon

        _icon = _stdicon(QStyle.SP_MediaPlay)
        self.setWindowIcon(_icon)

        _icon = _stdicon(QStyle.SP_DirOpenIcon)
        self.toolButtonOpenDir.setIcon(_icon)

        _icon = _stdicon(QStyle.SP_DialogOpenButton)
        self.toolButtonAskDir.setIcon(_icon)

    def _setup_ui(self):
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../mainwindow.ui')))
        self.setCentralWidget(self._ui)
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.labelVersion.setText('v{}'.format(__version__))
        self.resize(500, 700)
        self._setup_icon()
        self.tableView.setModel(self.control.model)
        self.tableView.setColumnWidth(0, 290)
        self.tableView.setColumnWidth(1, 80)
        self.tableView.setColumnWidth(2, 80)
        self.title = Title(self)
        self.on_data_changed()
        self.on_model_layout_changed()

    def _setup_signals(self):
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

        self.control.queue.stdout.connect(self.textBrowser.append)
        self.control.queue.stderr.connect(self.textBrowser.append)

        self.control.slave.progressed.connect(self.progressBar.setValue)
        self.control.slave.stopped.connect(self.on_slave_stopped)
        self.control.slave.finished.connect(self.on_slave_finished)
        self.control.slave.time_out.connect(self.on_slave_time_out)
        self.control.slave.progressed.connect(self._update_remains)
        self.control.root_changed.connect(self.on_root_changed)
        self.control.model.dataChanged.connect(self.on_data_changed)
        self.control.model.layoutChanged.connect(self.on_model_layout_changed)

        self.progressBar.valueChanged.connect(self.append_timestamp)

    def __init__(self, parent=None):

        super(MainWindow, self).__init__(parent)
        self.control = Controller(self)
        self._setup_ui()
        _link_edits_to_config({
            self.lineEditDir: 'DIR',
            self.checkBoxProxy: 'PROXY',
            self.checkBoxPriority: 'LOW_PRIORITY',
            self.checkBoxContinue: 'CONTINUE',
            self.comboBoxAfterFinish: 'AFTER_FINISH',
            self.doubleSpinBoxMemory: 'MEMORY_LIMIT',
            self.spinBoxTimeOut: 'TIME_OUT'
        })

        self._setup_signals()
        # Handle file drop
        self.setAcceptDrops(True)
        self.file_dropped.connect(self.on_file_dropped)

        # Handle key pressed
        # self.tableView.installEventFilter(self)

        self.control.change_root(CONFIG['DIR'])

    def __getattr__(self, name):
        return getattr(self._ui, name)

    def append_timestamp(self):
        """Create timestamp in text browser.  """

        self.textBrowser.append(stylize(time.strftime('[%x %X]'), 'info'))

    def on_root_changed(self, value):
        index = self.control.model.source_index(value)
        self.tableView.setRootIndex(index)

    def on_data_changed(self):
        self.pushButtonStart.setEnabled(
            any(self.control.model.checked_files()))
        self._update_remains()

    def _update_remains(self):
        """Set remains info on button: start, stop."""
        remains = self.control.queue.remains
        text = ('[{}]'.format(render.core.timef(int(remains)))
                if remains else '')
        self.pushButtonStart.setText('启动' + text)
        self.pushButtonStop.setText('停止' + text)

    def on_model_layout_changed(self):
        self.on_data_changed()
        self._update_button_remove_old_files()
        self._autostart()

    def _update_button_remove_old_files(self):
        button = self.pushButtonRemoveOldVersion
        old_files = list(self.control.model.old_version_files())
        button.setEnabled(bool(old_files))
        button.setToolTip('备份后从目录中移除低版本文件\n{}'.format(
            '\n'.join(old_files) or '<无>'))

    def _autostart(self):
        """Auto start rendering depend on setting.  """

        if (self._auto_start
                and not self.control.slave.rendering
                and self.control.queue):
            self._auto_start = False
            self.pushButtonStart.clicked.emit()
            LOGGER.info('发现新任务, 自动开始渲染')

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        path = QFileDialog.getExistingDirectory(
            dir=os.path.dirname(CONFIG['DIR']))
        if path:
            if self.check_dir(path):
                self.control.change_root(path)
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

    def on_file_dropped(self, files):
        files = [i for i in files if i.endswith('.nk')]
        if files:
            _ = [self.control.queue.put(i) for i in files]
            LOGGER.debug('Add %s', files)
        else:
            QMessageBox.warning(self, '不支持的格式', '目前只支持nk文件')

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
        self.textBrowser.clear()
        self.tabWidget.setCurrentIndex(1)

        self.control.start()

    @Slot()
    def on_stop_button_clicked(self):
        self.comboBoxAfterFinish.setCurrentIndex(0)

        self.control.stop()

    @Slot()
    def on_slave_stopped(self):
        self.pushButtonStop.hide()
        self.progressBar.hide()
        self.pushButtonStart.show()
        self.tabWidget.setCurrentIndex(0)
        QApplication.alert(self)

    @Slot()
    def on_slave_finished(self):

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
        widget = self.tableView
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
        if self.control.slave.rendering:
            confirm = QMessageBox.question(
                self,
                '正在渲染中',
                "停止渲染并退出?",
                QMessageBox.Yes |
                QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.control.slave.stop()

                def _on_stopped():
                    QApplication.exit()
                    LOGGER.info('渲染途中退出')
                self.control.slave.stopped.connect(_on_stopped)
            else:
                event.ignore()
        else:
            QApplication.exit()
            LOGGER.info('退出')

    # def eventFilter(self, widget, event):
    #     """Qt widget event filter.  """

    #     if (event.type() == QEvent.KeyPress and
    #             widget is self.tableView):
    #         key = event.key()

    #         if key == Qt.Key_Return:
    #             selected_task = self.task_table.current_selected()
    #             if len(selected_task) <= 1:
    #                 return True
    #             priority, confirm = QInputDialog.getInt(
    #                 self, '为所选设置优先级', '优先级')
    #             if confirm:
    #                 for task in selected_task:
    #                     task.priority = priority
    #                     self.task_table[task].update()
    #                 self.task_table.update_queue()
    #         return True
    #     return super(MainWindow, self).eventFilter(widget, event)


@Slot(QUrl)
def open_path(q_url):
    """Open file in console.  """
    path = q_url.toString()
    if not os.path.exists(path):
        path = os.path.dirname(path)
    webbrowser.open(path)
