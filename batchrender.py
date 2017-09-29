#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""
# TODO: title change when rendering
# TODO: file can change order manually
from __future__ import unicode_literals, print_function

import os
import sys
import re
import json
import logging
import logging.handlers
import time
import datetime
import shutil
import subprocess
import multiprocessing
import webbrowser


import singleton


__version__ = '0.8.4'
OS_ENCODING = __import__('locale').getdefaultlocale()[1]
LOGGER = logging.getLogger('batchrender')

if sys.getdefaultencoding() != 'UTF-8':
    reload(sys)
    sys.setdefaultencoding('UTF-8')


def _set_path():
    if sys.platform == 'win32':
        site_packages = os.path.join(os.path.dirname(
            sys.executable), r'pythonextensions\site-packages')
        sys.path.append(site_packages)


_set_path()
try:
    from Qt import QtWidgets, QtCore, QtCompat
    from Qt.QtWidgets import QMainWindow, QApplication, QFileDialog
except ImportError:
    raise


class Config(dict):
    """A config file can be manipulated that automatic write and read json file on disk."""

    default = {
        'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe',
        'DIR': r'E:\batchrender',
        'PROXY': 0,
        'LOW_PRIORITY': 2,
        'CONTINUE': 2,
        'HIBER': 0,
    }
    path = os.path.expanduser('~/.nuke/.batchrender.json')
    instance = None

    def __new__(cls):
        # Singleton
        if not cls.instance:
            cls.instance = super(Config, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        super(Config, self).__init__()
        self.update(dict(self.default))
        self.read()

    def __setitem__(self, key, value):
        LOGGER.debug('Config: %s = %s', key, value)
        if key == 'DIR' and value != self.get('DIR') and os.path.isdir(value):
            change_dir(value)
        dict.__setitem__(self, key, value)
        self.write()

    def write(self):
        """Write config to disk."""

        with open(self.path, 'w') as f:
            json.dump(self, f, indent=4, sort_keys=True)

    def read(self):
        """Read config from disk."""

        if os.path.isfile(self.path):
            with open(self.path) as f:
                self.update(dict(json.load(f)))


def _log_file():
    path = os.path.join(Config()['DIR'], 'Nuke批渲染.log')
    if os.path.exists(path):
        return path

    return os.path.join(os.getcwd(), 'Nuke批渲染.log')


def _set_logger(rollover=False):
    logger = logging.getLogger('batchrender')
    logger.propagate = False
    # Stream handler
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]: %(name)s: %(message)s', '%H:%M:%S')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    # File handler
    _path = _log_file()
    _handler = logging.handlers.RotatingFileHandler(
        _path, backupCount=5)
    if rollover and os.stat(_path).st_size > 10000:
        _handler.doRollover()
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

    return logger


def change_dir(dir_):
    """Try change currunt working directory."""

    try:
        os.chdir(get_unicode(dir_))
    except OSError:
        LOGGER.error(sys.exc_info()[2])
    LOGGER.info('工作目录改为: %s', os.getcwd())


class BatchRender(multiprocessing.Process):
    """Main render process."""
    LOG_FILENAME = 'Nuke批渲染.log'
    LOG_LEVEL = logging.INFO
    lock = multiprocessing.Lock()

    def __init__(self):
        multiprocessing.Process.__init__(self)
        self._queue = multiprocessing.Queue()

        self._config = Config()
        self._error_files = []
        self._files = Files()
        self.daemon = True

    def run(self):
        """(override)This function run in new process."""
        with self.lock:

            os.chdir(self._config['DIR'])
            self._files.unlock_all()
            self.continuous_render()

    def continuous_render(self):
        """Loop batch rendering as files exists."""

        while Files() and not Files().all_locked:
            self.batch_render()

    def batch_render(self):
        """Render all renderable file in dir."""

        for f in Files():
            _rtcode = self.render(f)

    def render(self, f):
        """Render a file with nuke."""
        title = '## [{}/{}]\t{}'.format(
            self._files.index(f) + 1,
            len(self._files), f)
        LOGGER.info(title)
        print('-' * 50)
        print(title)
        print('-' * 50)

        if not os.path.isfile(f):
            LOGGER.error('not isfile: %s', f)
            return False

        _rtcode = self.call_nuke(f)

        LOGGER.debug('Return code: %s', _rtcode)

        return _rtcode

    def call_nuke(self, f):
        """Open a nuke subprocess for rendering file."""

        time.clock()
        nk_file = Files.lock(f)

        _proxy = '-p ' if self._config['PROXY'] else '-f '
        _priority = '-c 8G --priority low ' if self._config['LOW_PRIORITY'] else ''
        _cont = '--cont ' if self._config['CONTINUE'] else ''
        cmd = '"{NUKE}" -x {}{}{} "{f}"'.format(
            _proxy,
            _priority,
            _cont,
            NUKE=self._config['NUKE'],
            f=nk_file
        )
        LOGGER.debug('命令: %s', cmd)
        _proc = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, cwd=Config()['DIR'], shell=True)
        self._queue.put(_proc.pid)
        while True:
            line = _proc.stderr.readline()
            if not line:
                break
            line = l10n(line)
            sys.stderr.write('STDERR: {}\n'.format(line))
            with open(_log_file(), 'a') as log:
                log.write('STDERR: {}\n'.format(line))
            _proc.stderr.flush()
        _proc.wait()
        _rtcode = _proc.returncode

        # Logging total time.
        LOGGER.info(
            '%s: 结束渲染 耗时 %s %s',
            f,
            timef(time.clock()),
            '退出码: {}'.format(_rtcode) if _rtcode else '正常退出',
        )

        if _rtcode:
            # Exited with error.
            self._error_files.append(f)
            _count = self._error_files.count(f)
            LOGGER.error('%s: 渲染出错 第%s次', f, _count)
            # TODO: retry limit
            if _count >= 3:
                # Not retry.
                LOGGER.error('%s: 连续渲染错误超过3次,不再进行重试。', f)
            else:
                Files.unlock(nk_file)
        else:
            # Normal exit.
            if not self._config['PROXY']:
                os.remove(nk_file)

        return _rtcode

    def stop(self):
        """Stop rendering."""

        _pid = None
        while not self._queue.empty():
            _pid = self._queue.get()
        if _pid:
            try:
                os.kill(_pid, 9)
            except OSError as ex:
                LOGGER.debug(ex)
        self.terminate()


def l10n(text):
    """Translate error info to chinese."""
    ret = text.strip('\r\n')

    with open(os.path.join(os.path.dirname(__file__), 'batchrender.zh_CN.json')) as f:
        translate_dict = json.load(f)
    for k, v in translate_dict.iteritems():
        ret = re.sub(k, v, ret)
    return ret


def timef(seconds):
    """Return a nice representation fo given seconds.

    >>> print(timef(10.123))
    10.123秒
    >>> print(timef(100))
    1分40秒
    >>> print(timef(100000))
    27小时46分40秒
    >>> print(timef(1.23456789))
    1.235秒
    """
    ret = ''
    hour = seconds // 3600
    minute = seconds % 3600 // 60
    seconds = round((seconds % 60 * 1000)) / 1000
    if int(seconds) == seconds:
        seconds = int(seconds)
    if hour:
        ret += '{}小时'.format(hour)
    if minute:
        ret += '{}分'.format(minute)
    ret += '{}秒'.format(seconds)
    return ret


def hiber():
    """Hibernate this computer.  """

    proc = subprocess.Popen('SHUTDOWN /H', stderr=subprocess.PIPE)
    stderr = get_unicode(proc.communicate()[1])
    LOGGER.error(stderr)
    if '没有启用休眠' in stderr:
        LOGGER.info('没有启用休眠, 转为使用关机')
        subprocess.call('SHUTDOWN /S')


class Files(list):
    """(Single instance)Files that need to be render.  """
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Files, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        super(Files, self).__init__()
        self.update()

    def update(self):
        """Update self from renderable files in dir.  """

        del self[:]
        _files = sorted([get_unicode(i) for i in os.listdir(os.getcwd())
                         if get_unicode(i).endswith(('.nk', '.nk.lock'))],
                        key=os.path.getmtime,
                        reverse=False)
        self.extend(_files)
        self.all_locked = self and all(bool(i.endswith('.lock')) for i in self)

    def unlock_all(self):
        """Unlock all .nk.lock files."""

        _files = [i for i in self if i.endswith('.nk.lock')]
        for f in _files:
            self.unlock(f)

    @staticmethod
    def unlock(f):
        """Rename a (raw_name).(ext) file back or delete it.  """

        _unlocked_name = os.path.splitext(f)[0]
        if os.path.isfile(_unlocked_name):
            os.remove(f)
            LOGGER.info('因为有更新的文件, 移除: %s', f)
        else:
            os.rename(f, _unlocked_name)
        return _unlocked_name

    @staticmethod
    def lock(f):
        """Duplicate given file with .lock append on name then archive it.  """

        if f.endswith('.lock'):
            return f

        Files.archive(f)
        locked_file = f + '.lock'
        os.rename(f, locked_file)
        return locked_file

    @staticmethod
    def archive(f, dest='文件备份'):
        """Archive file in a folder with time struture.  """

        now = datetime.datetime.now()
        weekday = ('周日', '周一', '周二', '周三', '周四', '周五', '周六')
        dest = os.path.join(
            dest,
            now.strftime('%Y年%m月'),
            now.strftime('%d日%H时%M分_{}/')
        ).format(weekday[int(now.strftime('%w'))])
        copy(f, dest)

    def remove_old_version(self):
        """Remove all old version nk files.  """

        all_version = {}
        while True:
            for i in self:
                if not os.path.exists(i):
                    continue
                shot, version = self.split_version(i)
                prev_version = all_version.get(shot, -2)
                if version > prev_version:
                    all_version[shot] = version
                    break
                elif version < prev_version:
                    self.archive(i)
                    os.remove(i)
            else:
                break

    @staticmethod
    def split_version(f):
        """Return nuke style _v# (shot, version number) pair.  """

        match = re.match(r'(.+)_v(\d+)', f)
        if not match:
            return (f, -1)
        shot, version = match.groups()
        if version < 0:
            raise ValueError('Negative version number not supported.')
        return (shot, version)


class MainWindow(QMainWindow):
    """Main GUI window.  """

    def __init__(self, parent=None):
        def _actions():
            self.actionRender.triggered.connect(self.render)
            self.actionDir.triggered.connect(self.ask_dir)
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
            os.path.join(__file__, '../mainwindow.ui')))
        self.setCentralWidget(self._ui)
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
        Files().unlock_all()

    def __getattr__(self, name):
        return getattr(self._ui, name)

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

        rendering = bool(self._proc and self._proc.is_alive())
        if not rendering and self.rendering:
            self.on_stop_callback()
        self.rendering = rendering
        _files = Files()

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
                    LOGGER.debug(ex)

        def _list_widget():
            self.listWidget.clear()
            for i in _files:
                self.listWidget.addItem('{}'.format(i))

        if not rendering and self.checkBoxAutoStart.isChecked() \
                and _files and not _files.all_locked:
            self.render()
        _edits()
        _list_widget()
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
        self._proc = BatchRender()
        self._proc.start()
        self.statusbar.showMessage('渲染中')

    @staticmethod
    def remove_old_version():
        """Remove old version nk files from UI.  """

        Files().remove_old_version()

    def stop(self):
        """Stop rendering from UI."""

        self.hiberCheck.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.checkBoxAutoStart.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self._proc.stop()

    def closeEvent(self, event):
        """Override qt closeEvent."""

        if self._proc and self._proc.is_alive():
            confirm = QtWidgets.QMessageBox.question(
                self,
                '正在渲染中',
                "停止渲染并退出?",
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


def copy(src, dst):
    """Copy src to dst."""

    LOGGER.info('\n复制:\n\t%s\n->\t%s', src, dst)
    if not os.path.exists(src):
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        LOGGER.debug('创建目录: %s', dst_dir)
        os.makedirs(dst_dir)
    try:
        shutil.copy2(src, dst)
    except OSError:
        if sys.platform == 'win32':
            subprocess.call('XCOPY /V /Y "{}" "{}"'.format(src, dst))
        else:
            raise
    if os.path.isdir(dst):
        ret = os.path.join(dst, os.path.basename(src))
    else:
        ret = dst
    return ret


def get_unicode(string, codecs=('GBK', 'UTF-8', OS_ENCODING)):
    """Return unicode by try decode @string with @codecs.  """

    if isinstance(string, unicode):
        return string

    for i in codecs:
        try:
            return unicode(string, i)
        except UnicodeDecodeError:
            continue


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
    args = (sys.executable, '--tg', _file)
    if sys.platform == 'win32':
        kwargs = {'creationflags': subprocess.CREATE_NEW_CONSOLE}
    else:
        args = '"{0[0]}" {0[1]} "{0[2]}"'.format(args)
        kwargs = {'shell': True, 'executable': 'bash'}
    subprocess.Popen(args,
                     cwd=render_dir,
                     **kwargs)


def main():
    """Run this script standalone."""
    _singleton = singleton.SingleInstance()
    _set_logger(True)

    try:
        os.chdir(Config()['DIR'])
    except OSError as ex:
        LOGGER.warning('Can not change dir')

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
