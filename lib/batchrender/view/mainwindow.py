# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import logging.handlers
import os
import subprocess
import sys
import webbrowser
from functools import wraps

import pendulum
from Qt import QtCompat
from Qt.QtCore import Qt, QUrl, Signal, Slot
from Qt.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                          QFileDialog, QInputDialog, QLineEdit, QMainWindow,
                          QMessageBox, QSpinBox, QStyle)

from ..__about__ import __version__
from ..actions import hiber, shutdown
from ..codectools import get_unicode as u
from ..config import CONFIG
from ..control import Controller
from ..mixin import UnicodeTrMixin
from ..texttools import stylize
from .outputlist import OutputListView
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
            LOGGER.debug('Widget not handled: %s %s', type(edit), edit)


class MainWindow(UnicodeTrMixin, QMainWindow):
    """Main GUI window.  """

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
        self.listView = OutputListView(self, self.control)
        self.listView.setModel(self.control.output_model)
        self.tab_3.layout().addWidget(self.listView)
        self.doubleSpinBoxMemory.setMaximum(CONFIG.default['MEMORY_LIMIT'])
        self.spinBoxThreads.setMaximum(CONFIG.default['THREADS'])

        self.title = Title(self.control, self)

        self.title.update()
        self.on_data_changed()
        self.on_model_layout_changed()

    def _setup_signals(self):
        self.lineEditDir.textChanged.connect(self.control.change_root)
        self.comboBoxAfterFinish.currentIndexChanged.connect(
            self.on_after_render_changed)

        self.toolButtonAskDir.clicked.connect(self.ask_dir)
        self.toolButtonOpenDir.clicked.connect(
            lambda: webbrowser.open(CONFIG['DIR']))
        self.toolButtonOpenLog.clicked.connect(
            lambda: webbrowser.open(CONFIG.log_path))
        self.toolButtonCheckAll.clicked.connect(self.control.enable_all)
        self.toolButtonRemove.clicked.connect(
            lambda: self.control.remove(self.tableView.selectedIndexes()))
        self.toolButtonReverseCheck.clicked.connect(
            self.control.invert_disable_state)

        self.selection_model.selectionChanged.connect(
            self.on_table_selection_changed)

        self.pushButtonStart.clicked.connect(self.on_start_button_clicked)
        self.pushButtonStop.clicked.connect(self.on_stop_button_clicked)

        self.textBrowser.anchorClicked.connect(open_path)
        self.listView.doubleClicked.connect(self.on_list_item_double_clicked)

        self.control.slave.stdout.connect(self.textBrowser.append)
        self.control.slave.stderr.connect(self.textBrowser.append)
        self.control.slave.progressed.connect(self.on_slave_progressed)
        self.control.slave.stopped.connect(self.on_slave_stopped)
        self.control.slave.finished.connect(self.on_slave_finished)
        self.control.slave.time_out.connect(self.on_slave_time_out)
        self.control.queue.remains_changed.connect(
            self.on_queue_remains_changed)
        self.control.root_changed.connect(self.on_root_changed)
        self.control.model.dataChanged.connect(self.on_data_changed)
        self.control.model.layoutChanged.connect(self.on_model_layout_changed)

    def __init__(self, parent=None):

        super(MainWindow, self).__init__(parent)
        self.control = Controller(self)
        self._is_auto_start = False
        self._setup_ui()
        _link_edits_to_config({
            self.lineEditDir: 'DIR',
            self.checkBoxProxy: 'PROXY',
            self.checkBoxPriority: 'LOW_PRIORITY',
            self.checkBoxContinue: 'CONTINUE',
            self.comboBoxAfterFinish: 'AFTER_FINISH',
            self.doubleSpinBoxMemory: 'MEMORY_LIMIT',
            self.spinBoxTimeOut: 'TIME_OUT',
            self.spinBoxThreads: 'THREADS'
        })

        self.selection_model = self.tableView.selectionModel()
        self._setup_signals()
        # Handle file drop
        self.setAcceptDrops(True)
        self.file_dropped.connect(self.on_file_dropped)

        # Handle key pressed
        # self.tableView.installEventFilter(self)

        self.control.change_root(CONFIG['DIR'])

    def __getattr__(self, name):
        return getattr(self._ui, name)

    def on_slave_progressed(self, value):
        self.progressBar.setValue(value)

    def on_root_changed(self, value):
        index = self.control.model.source_index(value)
        self.tableView.setRootIndex(index)

    def on_data_changed(self):
        self.pushButtonStart.setEnabled(
            any(self.control.model.iter_checked()))

    def on_table_selection_changed(self):
        self.toolButtonRemove.setEnabled(
            self.tableView.selectionModel().hasSelection())

    def on_queue_remains_changed(self, value):
        """Set remains info on button: start, stop."""

        text = ('[{}]'.format(pendulum.duration(
            seconds=value).in_words()) if value else '')
        self.pushButtonStart.setText(self.tr('Start') + text)
        self.pushButtonStop.setText(self.tr('Stop') + text)

    def on_model_layout_changed(self):
        self.on_data_changed()
        self._update_button_remove_old_files()
        self._autostart()

    def _update_button_remove_old_files(self):
        button = self.pushButtonRemoveOldVersion
        old_files = list(self.control.model.old_version_files())
        button.setEnabled(bool(old_files))
        button.setToolTip(self.tr('Archive old version files\n{}').format(
            '\n'.join(old_files) or self.tr('<None>')))

    def _autostart(self):
        """Auto start rendering depend on setting.  """

        if (self._is_auto_start
                and not self.control.slave.is_rendering
                and self.control.queue):
            self._is_auto_start = False
            self.control.start()
            LOGGER.info(self.tr('Found new task, auto start rendering.'))

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        path = QFileDialog.getExistingDirectory(
            dir=os.path.dirname(CONFIG['DIR']))
        if path:
            self.lineEditDir.setText(path)

    def on_file_dropped(self, files):
        files = [i for i in files if i.endswith('.nk')]
        if files:
            _ = [self.control.create_task(i) for i in files]
            LOGGER.debug('Add %s', files)
        else:
            QMessageBox.warning(self, self.tr(
                'Not support this file type.'), self.tr('Only support `.nk` file.'))

    def on_after_render_changed(self):
        edit = self.comboBoxAfterFinish
        text = edit.currentText()
        LOGGER.debug('After render change to %s', text)

        def _reset():
            edit.setCurrentIndex(0)

        def _deadline():
            if os.path.exists(CONFIG['DEADLINE']):
                LOGGER.info(
                    self.tr('Run deadline after render finished: %s'), CONFIG['DEADLINE'])
                return
            path = QFileDialog.getOpenFileName(
                self,
                self.tr('Choose Deadline Slave executable'),
                dir=CONFIG['DEADLINE'],
                filter='deadlineslave.exe;;*.*',
                selectedFilter='deadlineslave.exe')[0]
            if path:
                CONFIG['DEADLINE'] = path
                LOGGER.info(self.tr('Set Deadline path: %s'), path)
                edit.setToolTip(path)
            else:
                _reset()

        def _run_command():
            cmd, confirm = QInputDialog.getText(
                self, self.tr('Execute command after render finished...'),
                self.tr('Command'), text=CONFIG['AFTER_FINISH_CMD'])
            if confirm and cmd:
                CONFIG['AFTER_FINISH_CMD'] = cmd
                LOGGER.info(
                    self.tr('Execute command after render finished: %s'), cmd)
                edit.setToolTip(cmd)
            else:
                _reset()

        def _run_exe():
            path = QFileDialog.getOpenFileName(
                self, self.tr('Execute command after render finished...'),
                dir=CONFIG['AFTER_FINISH_PROGRAM'])[0]
            if path:
                CONFIG['AFTER_FINISH_PROGRAM'] = path
                LOGGER.info(
                    self.tr('Run program after render finished: %s'), path)
                edit.setToolTip(path)
            else:
                _reset()

        if text != self.tr('Wait for new task'):
            self._is_auto_start = False

        if text == self.tr('Deadline'):
            _deadline()
        elif text == self.tr('Execute command...'):
            _run_command()
        elif text == self.tr('Run program...'):
            _run_exe()
        else:
            edit.setToolTip('')

        if text in (self.tr('Shutdown'), self.tr('Hibernate'), self.tr('Deadline')):
            self.checkBoxPriority.setCheckState(Qt.Unchecked)
            self.spinBoxThreads.setValue(self.spinBoxThreads.maximum())
        else:
            self.checkBoxPriority.setCheckState(Qt.Checked)

    @Slot()
    def on_slave_time_out(self):
        """Wiil be excuted when frame take too long.  """

        msg = self.tr('Render timeout, remove resource limit.')
        LOGGER.info(msg)
        self.textBrowser.append(stylize(msg, 'error'))
        self.checkBoxPriority.setCheckState(Qt.Unchecked)
        self.spinBoxThreads.setValue(self.spinBoxThreads.maximum())
        self.doubleSpinBoxMemory.setValue(self.doubleSpinBoxMemory.maximum())
        self.spinBoxTimeOut.setValue(0)
        self._is_auto_start = True

    @Slot()
    def on_start_button_clicked(self):
        self.textBrowser.clear()
        self.tabWidget.setCurrentIndex(1)

        self.control.start()

    @Slot()
    def on_stop_button_clicked(self):
        self.comboBoxAfterFinish.setCurrentIndex(0)

        self.control.abort()

    def on_slave_stopped(self):
        QApplication.alert(self)
        self._autostart()

    def on_slave_finished(self):

        self.pushButtonStart.show()
        self.tabWidget.setCurrentIndex(0)
        self.pushButtonStop.hide()
        self.progressBar.hide()

        def reset_after_render(func):
            """(Decorator)Reset after render choice before run @func  ."""

            @wraps(func)
            def _func(*args, **kwargs):
                self.comboBoxAfterFinish.setCurrentIndex(0)
                return func(*args, **kwargs)
            return _func

        after_finish = self.comboBoxAfterFinish.currentText()

        actions = {
            self.tr('Wait for new task'): lambda: setattr(self, '_is_auto_start', True),
            self.tr('Hibernate'): reset_after_render(hiber),
            self.tr('Shutdown'): reset_after_render(shutdown),
            'Deadline': reset_after_render(lambda: webbrowser.open(CONFIG['DEADLINE'])),
            self.tr('Execute command...'):
                lambda: subprocess.Popen(
                    CONFIG['AFTER_FINISH_CMD'], shell=True),
            self.tr('Run program...'): lambda: webbrowser.open(CONFIG['AFTER_FINISH_PROGRAM']),
            self.tr('Idle'): lambda: LOGGER.info(self.tr('Idle after render finished.'))
        }

        actions.get(after_finish,
                    lambda: LOGGER.error('Not found match action for %s', after_finish))()

    def on_list_item_double_clicked(self, index):
        model = self.listView.model()
        item = model.data(index, Qt.EditRole)
        webbrowser.open(item.path.parent.as_posix())

    # Events.
    def dragEnterEvent(self, event):
        # LOGGER.debug('Drag into %s', self)
        if event.mimeData().urls():
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

        files = [u(i.toLocalFile()) for i in event.mimeData().urls()]
        LOGGER.debug('Dropped files: %s', ', '.join(files))
        self.file_dropped.emit(files)

    def closeEvent(self, event):
        if self.control.slave.is_rendering:
            confirm = QMessageBox.question(
                self,
                self.tr('Rendering'),
                self.tr("Stop render and exit?"),
                QMessageBox.Yes |
                QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.control.slave.stopped.connect(self.close)
                self.control.slave.abort()
            event.ignore()
            return

        event.accept()

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
