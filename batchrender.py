# -*- coding=UTF-8 -*-

import os
import sys
import re
import locale
import json
import logging
import datetime
import shutil
import time
from subprocess import Popen, PIPE, call
import multiprocessing
import threading

from PySide import QtGui, QtCore
from PySide.QtGui import QMainWindow, QApplication, QFileDialog

from ui_mainwindow import Ui_MainWindow

VERSION = 0.3
SYS_CODEC = locale.getdefaultlocale()[1]
TIME = datetime.datetime.now().strftime('%y%m%d_%H%M')
EXE_PATH = os.path.join(os.path.dirname(__file__), 'batchrender.exe')

class Config(dict):
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
        if not cls.instance:
            cls.instance = super(Config, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.update(dict(self.default))
        self.read()

    def __setitem__(self, key, value):
        if key == 'DIR' and value != self.get('DIR') and os.path.isdir(value):
            self.change_dir(value)
        dict.__setitem__(self, key, value)
        self.write()

    def write(self):
        with open(self.path, 'w') as f:
            json.dump(self, f, indent=4, sort_keys=True)

    def read(self):
        if os.path.isfile(self.path):
            with open(self.path) as f:
                self.update(dict(json.load(f)))

    def change_dir(self, dir):
        os.chdir(dir)
        print(u'工作目录改为: {}'.format(os.getcwd()))

class SingleInstanceException(Exception):
    def __str__(self):
        return u'已经有另一个实例在运行了'


class SingleInstance(object):
    def __init__(self):
        PID = Config()['PID']
        if isinstance(PID, int) and self.is_pid_exists(PID):
            raise SingleInstanceException
        Config()['PID'] = os.getpid()

    def is_pid_exists(self, pid):
        if sys.platform == 'win32':
            _proc = Popen('TASKLIST /FI "PID eq {}" /FO CSV /NH'.format(pid), stdout=PIPE)
            _stdout = _proc.communicate()[0]
            return '"{}"'.format(pid) in _stdout

class Logger(logging.Logger):
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Logger, cls).__new__(cls)
        return cls.instance

class BatchRender(multiprocessing.Process):
    LOG_FILENAME = u'Nuke批渲染.log'
    LOG_LEVEL = logging.DEBUG
    lock = multiprocessing.Lock()

    def __init__(self):
        multiprocessing.Process.__init__(self)
        self._queue = multiprocessing.Queue()

        self._config = Config()
        self._error_files = []
        self._files = Files()
        self.daemon = True

    def run(self):
        self.rotate_log()
        self.set_logger()
        self.lock.acquire()
        self._files.unlock_all()
        self.batch_render()
        self.lock.release()

    def continuous_render(self):
        while self.files():
            self.batch_render()

    def set_logger(self):
        self._logfile = open(self.LOG_FILENAME, 'a')
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(self.LOG_LEVEL)
        handler = logging.FileHandler(self.LOG_FILENAME)
        formatter = logging.Formatter('[%(asctime)s]\t%(levelname)10s:\t%(message)s')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def rotate_log(self):
        if os.path.isfile(self.LOG_FILENAME):
            if os.stat(self.LOG_FILENAME).st_size > 10000:
                logname = os.path.splitext(self.LOG_FILENAME)[0]
                # Remove oldest logfile.
                if os.path.exists(u'{}.{}.log'.format(logname, 5)):
                    os.remove(u'{}.{}.log'.format(logname, 5))
                # Rename else.
                for i in range(5)[:0:-1]:
                    old_name = u'{}.{}.log'.format(logname, i)
                    new_name = u'{}.{}.log'.format(logname, i+1)
                    if os.path.exists(old_name):
                        os.rename(old_name, new_name)
                os.rename(self.LOG_FILENAME, u'{}.{}.log'.format(logname, 1))


    def batch_render(self):
        self._logger.info('{:-^50s}'.format('<开始批渲染>'))
        for file in Files():
            _rtcode = self.render(file)

        self._logger.info('<结束批渲染>')
        if Config()['HIBER']:
            self._logger.info('<计算机进入休眠模式>')
            hiber()

    def render(self, file):
        print(u'## [{}/{}]\t{}'.format(self._files.index(file) + 1, len(self._files), file))
        self._logger.info(u'{}: 开始渲染'.format(file))

        if not os.path.isfile(file):
            print('not isfile', file)
            return False

        _rtcode = self.call_nuke(file)
        print('\n')
        print('_retcode', _rtcode)

        return _rtcode

    def call_nuke(self, file):
        _time = datetime.datetime.now()
        _file = Files.lock(file)

        _proxy = '-p ' if self._config['PROXY'] else '-f '
        _priority = '-c 8G --priority low ' if self._config['LOW_PRIORITY'] else ''
        _cont = '--cont ' if self._config['CONTINUE'] else ''
        cmd = u'"{NUKE}" -x {}{}{} "{file}"'.format(
            _proxy,
            _priority,
            _cont,
            NUKE=self._config['NUKE'],
            file=_file,
        )
        self._logger.debug(u'命令: {}'.format(cmd))
        print(cmd)
        _proc = Popen(cmd.encode('UTF-8'), stderr=PIPE)
        self._queue.put(_proc.pid)
        _stderr = _proc.communicate()[1]
        _stderr = self.convert_error_value(_stderr)
        if _stderr:
            sys.stderr.write(_stderr)
            if re.match(r'\[.*\] Warning: (.*)', _stderr):
                self._logger.warning(_stderr)
            else:
                self._logger.error(_stderr)

        _rtcode = _proc.returncode

        # Logging total time.
        self._logger.info(u'{}: 结束渲染 耗时 {} {}'.format(
            file,
            self.format_seconds((datetime.datetime.now() - _time).total_seconds()),
            u'退出码: {}'.format(_rtcode) if _rtcode else u'正常退出',
        ))

        if _rtcode:
            # Exited with error.
            self._error_files.append(file)
            _count = self._error_files.count(file)
            self._logger.error(u'{}: 渲染出错 第{}次'.format(file, _count))
            if _count >= 3:
                # Not retry.
                self._logger.error(u'{}: 连续渲染错误超过3次,不再进行重试。'.format(file))
            elif os.path.isfile(file):
                # Retry, use new version.
                os.remove(_file)
            else:
                # Retry, use this version.
                os.rename(_file, file)
        else:
            # Normal exit.
            if not self._config['PROXY']:
                os.remove(_file)

        return _rtcode

    def convert_error_value(self, str):
        ret = str.strip('\r\n')
        ret = re.sub(r'\[.*?\] ERROR: (.+)', r'\1', ret)
        ret = ret.replace(
            'Read error: No such file or directory',
            '读取错误: 找不到文件或路径'
        )
        ret = ret.replace(
            'Missing input channel',
            '输入通道丢失'
        )
        ret = ret.replace(
            'There are no active Write operators in this script',
            '此脚本中没有启用任何Write节点'
        )
        ret = re.sub(
            r'(.+?: )Error reading LUT file\. (.+?: )unable to open file\.',
            r'\1读取LUT文件出错。 \2 无法打开文件',
            ret
        )
        ret = re.sub(
            r'(.+?: )Error reading pixel data from image file (".*")\. Scan line (.+?) is missing\.',
            r'\1自文件 \2 读取像素数据错误。扫描线 \3 丢失。',
            ret
        )
        ret = re.sub(
            r'(.+?: )Error reading pixel data from image file (".*")\. Early end of file: read (.+?) out of (.+?) requested bytes.',
            r'\1自文件 \2 读取像素数据错误。过早的文件结束符: 读取了 \4 数据中的 \3 。',
            ret
        )
        try:
            ret = unicode(ret, 'UTF-8')
        except UnicodeDecodeError:
            ret = unicode(ret, SYS_CODEC)
        return ret

    def format_seconds(self, seconds):
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

    def stop(self):
        while not self._queue.empty():
            _pid = self._queue.get()
        if _pid:
            try:
                os.kill(_pid, 9)
            except WindowsError as e:
                print(e)
        self.terminate()

def hiber():
    call(['SHUTDOWN', '/h'])

class Files(list):
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Files, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        del self[:]
        self.extend(self.files())
    
    def files(self):
        _files = os.listdir(os.getcwd())
        _files = filter(lambda x: x.endswith(('.nk', '.nk.lock')), _files)
        _files = map(lambda x: unicode(x, SYS_CODEC), _files)
        _files.sort(key=lambda file: os.path.getmtime(file), reverse=False)

        return _files

    def unlock_all(self):
        _files = filter(lambda x: x.endswith('.nk.lock'), self)
        for f in _files:
            self.unlock(f)

    @staticmethod
    def unlock(file):
        if isinstance(file, unicode):
            file = file.encode(SYS_CODEC)
        _unlocked_name = os.path.splitext(file)[0]
        if os.path.isfile(_unlocked_name):
            os.remove(file)
            self._logger.info(u'因为有更新的文件, 移除: {}'.format(file))
        else:
            os.rename(file, _unlocked_name)
        return unicode(_unlocked_name, SYS_CODEC)
                
    @staticmethod
    def lock(file):
        if isinstance(file, unicode):
            file = file.encode(SYS_CODEC)
        locked_file = file + '.lock'
        file_archive_folder = os.path.join('ArchivedRenderFiles', TIME)
        file_archive_dest = os.path.join(file_archive_folder, file)

        shutil.copyfile(file, locked_file)
        if not os.path.exists(file_archive_folder):
            os.makedirs(file_archive_folder)
        if os.path.exists(file_archive_dest):
            time_text = datetime.datetime.fromtimestamp(os.path.getctime(file_archive_dest)).strftime('%M%S_%f')
            alt_file_archive_dest = file_archive_dest + '.' + time_text
            if os.path.exists(alt_file_archive_dest):
                os.remove(file_archive_dest)
            else:
                os.rename(file_archive_dest, alt_file_archive_dest)
        shutil.move(file, file_archive_dest)
        return unicode(locked_file, SYS_CODEC)
    
class MainWindow(QMainWindow, Ui_MainWindow, SingleInstance):

    def __init__(self, parent=None):
        def _actions():
            self.actionRender.triggered.connect(self.render)
            self.actionDir.triggered.connect(self.ask_dir)
            self.actionNuke.triggered.connect(self.ask_nuke)
            self.actionStop.triggered.connect(self.stop)

        def _edits():
            self.dirEdit.textChanged.connect(lambda dir: self.change_dir(dir))

            for edit, key in self.edits_key.iteritems():
                if isinstance(edit, QtGui.QLineEdit):
                    edit.textChanged.connect(lambda text, k=key: self._config.__setitem__(k, text))
                elif isinstance(edit, QtGui.QCheckBox):
                    edit.stateChanged.connect(lambda state, k=key: self._config.__setitem__(k, state))
                elif isinstance(edit, QtGui.QComboBox):
                    edit.currentIndexChanged.connect(lambda index, e=edit, k=key: self._config.__setitem__(k, e.itemText(index)))
                else:
                    print(u'待处理的控件: {} {}'.format(type(edit), edit))

        SingleInstance.__init__(self)
        QMainWindow.__init__(self, parent)
        self.setupUi(self)

        self._config = Config()
        self._proc = None

        self.edits_key = {  
            self.dirEdit: 'DIR',
            self.nukeEdit: 'NUKE',
            self.proxyCheck: 'PROXY',
            self.priorityCheck: 'LOW_PRIORITY',
            self.continueCheck: 'CONTINUE',
            self.hiberCheck: 'HIBER',
        }
        os.chdir(self._config['DIR'])
        self.update()
        self.update_threading()
        self.versionLabel.setText('v{}'.format(VERSION))

        _actions()
        _edits()
        Files().unlock_all()

    def update_threading(self):
        _timer = QtCore.QTimer(self)
        _timer.timeout.connect(self.update)
        _timer.start(1000)

    def update(self):
        def _button_enabled():
            if self._proc and self._proc.is_alive():
                self.renderButton.setEnabled(False)
                self.stopButton.setEnabled(True)
            else:
                if os.path.isdir(self._config['DIR']):
                    self.renderButton.setEnabled(True)
                self.stopButton.setEnabled(False)

        def _edits():
            for q, k in self.edits_key.iteritems():
                try:
                    if isinstance(q, QtGui.QLineEdit):
                        q.setText(self._config[k])
                    if isinstance(q, QtGui.QCheckBox):
                        q.setCheckState(QtCore.Qt.CheckState(self._config[k]))
                except KeyError as e:
                    print(e)

        def _list_widget():
            list = self.listWidget
            list.clear()
            for i in Files():
                list.addItem(u'{}'.format(i))

        _edits()
        _list_widget()
        _button_enabled()

    def ask_dir(self):
        _fileDialog = QFileDialog()
        _dir = _fileDialog.getExistingDirectory(dir=os.path.dirname(self._config['DIR']))
        if _dir:
            self._config['DIR'] = _dir
            self.update()

    def ask_nuke(self):
        _fileDialog = QFileDialog()
        _fileNames, _selectedFilter = fileDialog.getOpenFileName(dir=os.getenv('ProgramFiles'), filter='*.exe')
        if _fileNames:
            self._config['NUKE'] = _fileNames
            self.update()

    def render(self):
        self._proc = BatchRender()
        self._proc.start()
        
    def stop(self):
        self._config['HIBER'] = 0 
        self._proc.stop()
        print(u'# 停止渲染')
    
    def closeEvent(self, event):
        if self._proc and self._proc.is_alive():
            _ok = QtGui.QMessageBox.question(
                self,
                u'正在渲染中',
                u"停止渲染并退出?",
                QtGui.QMessageBox.Yes |
                QtGui.QMessageBox.No,
                QtGui.QMessageBox.No
            )
            if _ok == QtGui.QMessageBox.Yes:
                self._proc.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    reload(sys)
    sys.setdefaultencoding('UTF-8')
    call(u'CHCP 936 & TITLE BatchRender{} & CLS'.format(VERSION), shell=True)
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())

def pause():
    call('PAUSE', shell=True)

if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        exit(e)
    except SingleInstanceException as e:
        print(u'激活已经打开的实例')
        Popen('"{}" "{}"'.format(os.path.join(__file__, '../active_pid.exe'), format(Config()['PID'])))
    except:
        import traceback
        traceback.print_exc()
