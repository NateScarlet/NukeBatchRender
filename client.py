# -*- coding=UTF-8 -*-
"""Batch render client."""
import os
import sys
import time
from subprocess import Popen
from multiprocessing.connection import Client

from Qt import QtWidgets, QtCompat, QtCore
from Qt.QtWidgets import QMainWindow, QFileDialog, QApplication

import server
import path

__version__ = '0.8.0'


def send(obj):
    """Send @obj to server.  """
    conn = Client(server.ADDRESS, authkey=server.AUTH_KEY)
    conn.send(obj)
    ret = conn.recv()
    if ret != server.Server.CLOSE:
        conn.send(server.Server.CLOSE)
    conn.close()
    return ret


class MainWindow(QMainWindow):
    """Main GUI window.  """

    def __init__(self, parent=None):
        def _actions():
            self.actionRender.triggered.connect(self.render)
            self.actionDir.triggered.connect(self.ask_dir)
            self.actionNuke.triggered.connect(self.ask_nuke)
            self.actionStop.triggered.connect(self.stop)
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
                    print(u'待处理的控件: {} {}'.format(type(edit), edit))

        def _icon():
            _stdicon = self.style().standardIcon

            _icon = _stdicon(QtWidgets.QStyle.SP_MediaPlay)
            self.setWindowIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DirOpenIcon)
            self.toolButtonOpenDir.setIcon(_icon)

            _icon = _stdicon(QtWidgets.QStyle.SP_DialogOpenButton)
            self.toolButtonDir.setIcon(_icon)
            self.toolButtonNuke.setIcon(_icon)

        QMainWindow.__init__(self, parent)
        self._ui = QtCompat.loadUi(os.path.abspath(
            os.path.join(__file__, '../mainwindow.ui')))

        self._config = send(server.Command('get_config'))
        self._proc = None
        self.rendering = False

        self.edits_key = {
            self.dirEdit: 'DIR',
            self.nukeEdit: 'NUKE',
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

    def __getattr__(self, name):
        return getattr(self._ui, name)

    def open_dir(self):
        """Open dir in explorer.  """

        url_open(self._config['DIR'], isfile=True)

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

        rendering = bool(self._proc and self._proc.is_alive())
        if not rendering and self.rendering:
            self.on_stop_callback()
        self.rendering = rendering
        _files = send(server.Command('get_files'))

        def _button_enabled():
            if rendering:
                self.renderButton.setEnabled(False)
                self.stopButton.setEnabled(True)
                self.listWidget.setStyleSheet(
                    'color:white;background-color:rgb(12%, 16%, 18%);')
                self.pushButtonRemoveOldVersion.setEnabled(False)
            else:
                if os.path.isdir(self._config['DIR']) and _files:
                    self.renderButton.setEnabled(True)
                else:
                    self.renderButton.setEnabled(False)
                self.stopButton.setEnabled(False)
                self.listWidget.setStyleSheet('')
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
                    print(ex)

        def _list_widget():
            self.listWidget.clear()
            for i in _files:
                self.listWidget.addItem(u'{}'.format(i))

        if not rendering and self.checkBoxAutoStart.isChecked() \
                and _files and not _files.all_locked:
            self.render()
        _edits()
        _list_widget()
        _button_enabled()

    def ask_dir(self):
        """Show a dialog ask config['DIR'].  """

        dialog = QFileDialog()
        dir_ = dialog.getExistingDirectory(
            dir=os.path.dirname(self._config['DIR']))
        if dir_:
            try:
                dir_.encode('ascii')
            except UnicodeEncodeError:
                self.statusbar.showMessage(u'Nuke只支持英文路径', 10000)
            else:
                self._config['DIR'] = dir_

    def ask_nuke(self):
        """Show a dialog ask config['NUKE'].  """

        dialog = QFileDialog()
        filenames = dialog.getOpenFileName(
            dir=os.getenv('ProgramFiles'), filter='*.exe')[0]
        if filenames:
            self._config['NUKE'] = filenames
            print('test')
            self.update()

    def stop(self):
        """Stop rendering from UI."""

        self.hiberCheck.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.checkBoxAutoStart.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self._proc.stop()
        self.statusbar.showMessage(time_prefix(u'停止渲染'))

    def closeEvent(self, event):
        """Override qt closeEvent."""

        if self._proc and self._proc.is_alive():
            confirm = QtWidgets.QMessageBox.question(
                self,
                u'正在渲染中',
                u"停止渲染并退出?",
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if confirm == QtWidgets.QMessageBox.Yes:
                self._proc.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def remove_old_version(self):
        send(server.Command('remove_old_version'))

    def on_stop_callback(self):
        """Do work when rendering stop.  """

        QApplication.alert(self)
        self.statusbar.showMessage(time_prefix(u'渲染已完成'))
        if self.hiberCheck.isChecked():
            self.statusbar.showMessage(time_prefix(u'休眠'))
            self.hiberCheck.setCheckState(QtCore.Qt.CheckState.Unchecked)
            send(server.Command('hiber'))


def time_prefix(text):
    """Insert time before @text.  """
    return u'[{}]{}'.format(time.strftime('%X'), text)


def url_open(url, isfile=False):
    """Open url in explorer. """
    if isfile:
        url = u'file://{}'.format(url)
    _cmd = u"rundll32.exe url.dll,FileProtocolHandler {}".format(url)
    Popen(path.get_encoded(_cmd))


def main():
    """Script entry.  """
    server.start()
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
