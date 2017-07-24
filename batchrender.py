# -*- coding=UTF-8 -*-
"""
GUI Batchrender for nuke.
"""

import os
import sys
import re
import json
import logging
import datetime
import shutil
import time
import locale
from subprocess import Popen, PIPE, call
import multiprocessing

from PySide import QtGui, QtCore
from PySide.QtGui import QMainWindow, QApplication, QFileDialog

from ui_mainwindow import Ui_MainWindow


__version__ = '0.7.19'
EXE_PATH = os.path.join(os.path.dirname(__file__), 'batchrender.exe')
OS_ENCODING = locale.getdefaultlocale()[1]

reload(sys)
sys.setdefaultencoding('UTF-8')


class Config(dict):
    """A config file can be manipulated that automatic write and read json file on disk."""

    default = {
        'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe',
        'DIR': r'E:\batchrender',
        'PROXY': 0,
        'LOW_PRIORITY': 2,
        'CONTINUE': 2,
        'HIBER': 0,
        'PID': None,
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
        print(key, value)
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


def change_dir(dir_):
    """Try change currunt working directory."""

    try:
        os.chdir(get_unicode(dir_))
    except WindowsError:
        print(sys.exc_info()[2])
    print(u'工作目录改为: {}'.format(get_unicode(os.getcwd())))


class SingleInstanceException(Exception):
    """Indicate not single instance."""

    def __str__(self):
        return u'已经有另一个实例在运行了'


def check_single_instance():
    """Raise SingleInstanceException if not run in singleinstance."""

    pid = Config()['PID']
    if isinstance(pid, int) and is_pid_exists(pid):
        raise SingleInstanceException
    Config()['PID'] = os.getpid()


def is_pid_exists(pid):
    """Check if pid existed.(Windows only)"""

    if sys.platform == 'win32':
        _proc = Popen(
            'TASKLIST /FI "PID eq {}" /FO CSV /NH'.format(pid),
            stdout=PIPE
        )
        _stdout = _proc.communicate()[0]
        ret = '"{}"'.format(pid) in _stdout
        if ret:
            print(_stdout)
        return ret


class BatchRender(multiprocessing.Process):
    """Main render process."""
    LOG_FILENAME = u'Nuke批渲染.log'
    LOG_LEVEL = logging.INFO
    lock = multiprocessing.Lock()

    def __init__(self):
        multiprocessing.Process.__init__(self)
        self._queue = multiprocessing.Queue()

        self._config = Config()
        self._error_files = []
        self._files = Files()
        self._logger = None
        self.daemon = True

    def run(self):
        """(override)This function run in new process."""

        reload(sys)
        sys.setdefaultencoding('UTF-8')

        with self.lock:

            self.set_logger()
            os.chdir(self._config['DIR'])
            self._files.unlock_all()
            self.continuous_render()

    def set_logger(self):
        """Set logger for this process."""

        self.rotate_log()
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(self.LOG_LEVEL)
        handler = logging.FileHandler(self.LOG_FILENAME)
        formatter = logging.Formatter(
            '[%(asctime)s]\t%(levelname)10s:\t%(message)s')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def continuous_render(self):
        """Loop batch rendering as files exists."""

        while Files() and not Files().all_locked:
            self.batch_render()

    def rotate_log(self):
        """Rotate existed logfile if needed."""

        prefix = os.path.splitext(self.LOG_FILENAME)[0]
        if os.path.isfile(self.LOG_FILENAME) and os.stat(self.LOG_FILENAME).st_size > 10000:
            for i in range(4, 0, -1):
                old_name = u'{}.{}.log'.format(prefix, i)
                new_name = u'{}.{}.log'.format(prefix, i + 1)
                if os.path.exists(old_name):
                    if os.path.exists(new_name):
                        os.remove(new_name)
                    os.rename(old_name, new_name)
            os.rename(self.LOG_FILENAME, old_name)

    def batch_render(self):
        """Render all renderable file in dir."""

        self._logger.info('{:-^50s}'.format('<开始批渲染>'))
        for f in Files():
            _rtcode = self.render(f)

        self._logger.info('<结束批渲染>')

    def render(self, f):
        """Render a file with nuke."""

        print(u'## [{}/{}]\t{}'.format(self._files.index(f) +
                                       1, len(self._files), f))
        self._logger.info(u'%s: 开始渲染', f)

        if not os.path.isfile(f):
            print('not isfile', f)
            return False

        _rtcode = self.call_nuke(f)
        print('\n')
        print('_retcode', _rtcode)

        return _rtcode

    def call_nuke(self, f):
        """Open a nuke subprocess for rendering file."""

        current_time = datetime.datetime.now()
        nk_file = Files.lock(f)

        _proxy = '-p ' if self._config['PROXY'] else '-f '
        _priority = '-c 8G --priority low ' if self._config['LOW_PRIORITY'] else ''
        _cont = '--cont ' if self._config['CONTINUE'] else ''
        cmd = u'"{NUKE}" -x {}{}{} "{f}"'.format(
            _proxy,
            _priority,
            _cont,
            NUKE=self._config['NUKE'],
            f=nk_file
        )
        self._logger.debug(u'命令: %s', cmd)
        print(cmd)
        _proc = unicode_popen(cmd, stderr=PIPE)
        self._queue.put(_proc.pid)
        _stderr = _proc.communicate()[1]
        _stderr = fanyi(_stderr)
        if _stderr:
            sys.stderr.write(_stderr)
            if re.match(r'\[.*\] Warning: (.*)', _stderr):
                self._logger.warning(_stderr)
            else:
                self._logger.error(_stderr)

        _rtcode = _proc.returncode

        # Logging total time.
        self._logger.info(
            u'%s: 结束渲染 耗时 %s %s',
            f,
            timef((datetime.datetime.now() - current_time).total_seconds()),
            u'退出码: {}'.format(_rtcode) if _rtcode else u'正常退出',
        )

        if _rtcode:
            # Exited with error.
            self._error_files.append(f)
            _count = self._error_files.count(f)
            self._logger.error(u'%s: 渲染出错 第%s次', f, _count)
            # TODO: retry limit
            if _count >= 3:
                # Not retry.
                self._logger.error(u'%s: 连续渲染错误超过3次,不再进行重试。', f)
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
            except WindowsError as ex:
                print(ex)
        self.terminate()


def fanyi(text):
    """Translate error info to chinese."""
    ret = text.strip('\r\n')

    with open(os.path.join(__file__, '../batchrender.zh_CN.json')) as f:
        translate_dict = json.load(f)
    for k, v in translate_dict.iteritems():
        ret = re.sub(k, v, ret)
    return ret


def timef(seconds):
    """Return a nice representation fo given seconds."""
    ret = u''
    hour = int(seconds // 3600)
    minute = int(seconds % 3600 // 60)
    seconds = seconds % 60
    if hour:
        ret += u'{}小时'.format(hour)
    if minute:
        ret += u'{}分钟'.format(minute)
    ret += u'{}秒'.format(seconds)
    return ret


def hiber():
    """Hibernate this computer.  """

    call(['SHUTDOWN', '/h'])


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
        _files = sorted([get_unicode(i) for i in os.listdir(
            os.getcwd()) if i.endswith(('.nk', '.nk.lock'))], key=os.path.getmtime, reverse=False)
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
            print(u'因为有更新的文件, 移除: {}'.format(f))
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
    def archive(f, dest=u'文件备份'):
        """Archive file in a folder with time struture.  """

        now = datetime.datetime.now()
        weekday = ('周日', '周一', '周二', '周三', '周四', '周五', '周六')
        dest = os.path.join(
            dest,
            get_unicode(now.strftime(u'%Y年%m月')),
            get_unicode(now.strftime(u'%d日%H时%M分_{}/'))
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


class MainWindow(QMainWindow, Ui_MainWindow):
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
                if isinstance(edit, QtGui.QLineEdit):
                    edit.textChanged.connect(
                        lambda text, k=key: self._config.__setitem__(k, text))
                elif isinstance(edit, QtGui.QCheckBox):
                    edit.stateChanged.connect(
                        lambda state, k=key: self._config.__setitem__(k, state))
                elif isinstance(edit, QtGui.QComboBox):
                    edit.currentIndexChanged.connect(
                        lambda index, ex=edit, k=key:
                        self._config.__setitem__(k, ex.itemText(index)))
                else:
                    print(u'待处理的控件: {} {}'.format(type(edit), edit))

        def _icon():
            _stdicon = self.style().standardIcon

            _icon = _stdicon(QtGui.QStyle.SP_MediaPlay)
            self.setWindowIcon(_icon)

            _icon = _stdicon(QtGui.QStyle.SP_DirOpenIcon)
            self.toolButtonOpenDir.setIcon(_icon)

            _icon = _stdicon(QtGui.QStyle.SP_DialogOpenButton)
            self.toolButtonDir.setIcon(_icon)
            self.toolButtonNuke.setIcon(_icon)

        check_single_instance()
        QMainWindow.__init__(self, parent)
        self.setupUi(self)

        self._config = Config()
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
        Files().unlock_all()

    def open_dir(self):
        """Open dir in explorer.  """

        url_open(file_url(self._config['DIR']))

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
                    if isinstance(qt_edit, QtGui.QLineEdit):
                        qt_edit.setText(self._config[k])
                    if isinstance(qt_edit, QtGui.QCheckBox):
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

    def on_stop_callback(self):
        """Do work when rendering stop.  """

        QApplication.alert(self)
        self.statusbar.showMessage(time_prefix(u'渲染已完成'))
        if self.hiberCheck.isChecked():
            self.statusbar.showMessage(time_prefix(u'休眠'))
            self._config['HIBER'] = False
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

    def render(self):
        """Start rendering from UI.  """

        _file = os.path.abspath(os.path.join(__file__, '../error_handler.exe'))
        url_open(file_url(_file))
        self._proc = BatchRender()
        self._proc.start()
        self.statusbar.showMessage(u'渲染中')

    @staticmethod
    def remove_old_version():
        """Remove old version nk files from UI.  """

        Files().remove_old_version()

    def stop(self):
        """Stop rendering from UI."""

        self._config['HIBER'] = 0
        self._proc.stop()
        self.checkBoxAutoStart.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.statusbar.showMessage(time_prefix(u'停止渲染'))

    def closeEvent(self, event):
        """Override qt closeEvent."""

        if self._proc and self._proc.is_alive():
            confirm = QtGui.QMessageBox.question(
                self,
                u'正在渲染中',
                u"停止渲染并退出?",
                QtGui.QMessageBox.Yes |
                QtGui.QMessageBox.No,
                QtGui.QMessageBox.No
            )
            if confirm == QtGui.QMessageBox.Yes:
                self._proc.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def time_prefix(text):
    """Insert time before @text.  """
    return u'[{}]{}'.format(time.strftime('%H:%M:%S'), text)


def main():
    """Run this script standalone."""
    import fix_pyinstaller
    fix_pyinstaller.main()
    call(u'@TITLE batchrender.console', shell=True)
    try:
        os.chdir(Config()['DIR'])
    except WindowsError:
        print(sys.exc_info())
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())


def pause():
    """Pause prompt with a countdown."""

    print(u'')
    for i in range(5)[::-1]:
        sys.stdout.write(u'\r{:2d}'.format(i + 1))
        time.sleep(1)
    sys.stdout.write(u'\r          ')
    print(u'')


def copy(src, dst):
    """Copy src to dst."""
    message = u'{} -> {}'.format(src, dst)
    print(message)
    if not os.path.exists(src):
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    shutil.copy2(src, dst)


def url_open(url):
    """Open url in explorer. """

    _cmd = u'rundll32.exe url.dll,FileProtocolHandler "{}"'.format(url)
    unicode_popen(_cmd)


def get_unicode(string, codecs=('UTF-8', OS_ENCODING)):
    """Return unicode by try decode @string with @codecs.  """

    if isinstance(string, unicode):
        return string

    for i in codecs:
        try:
            return unicode(string, i)
        except UnicodeDecodeError:
            continue


def unicode_popen(args, **kwargs):
    """Return Popen object use encoded args.  """

    if isinstance(args, unicode):
        args = args.encode(OS_ENCODING)
    return Popen(args, **kwargs)


def file_url(text):
    """Left append 'file://' to @text.  """

    return 'file://{}'.format(text)


if __name__ == '__main__':
    __file__ = os.path.abspath(sys.argv[0])
    try:
        main()
    except SystemExit as ex:
        sys.exit(ex)
    except SingleInstanceException as ex:
        print(u'激活已经打开的实例 pid:{}'.format(Config()['PID']))
        Popen('"{}" "{}"'.format(os.path.join(
            __file__, '../active_pid.exe'), format(Config()['PID'])))
        pause()
