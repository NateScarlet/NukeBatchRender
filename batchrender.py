# -*- coding=UTF-8 -*-

import os
import sys
import re
import locale
import json
import logging
import datetime
import shutil
from subprocess import Popen, PIPE, call
import multiprocessing

import PySide
import PySide.QtCore
import PySide.QtGui
from PySide.QtGui import QMainWindow, QApplication, QFileDialog

from ui_MainWindow import Ui_MainWindow

VERSION = 0.22
SYS_CODEC = locale.getdefaultlocale()[1]
TIME = datetime.datetime.now().strftime('%y%m%d_%H%M')
EXE_PATH = os.path.join(os.path.dirname(__file__), 'batchrender.exe')

class Config(dict):
    default = {
                'SERVER': r'\\192.168.1.7\z', 
                'SIMAGE_FOLDER': r'Comp\image', 
                'SVIDEO_FOLDER': r'Comp\mov', 
                'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe', 
                'DIR': r'E:\test\batchRender', 
                'PROJECT': 'SNJYW', 
                'EP': '', 
                'SCENE': '', 
                'PROXY': 0, 
                'LOW_PRIORITY': 0, 
                'CONTINUE': 2, 
                'PID': None,
             }
    path = os.path.join(os.getenv('UserProfile'), '.BatchRender.json')

    def __init__(self):
        self.update(dict(self.default))
        self.read()            

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.write()

    def write(self):
        with open(self.path, 'w') as f:
            json.dump(self, f, indent=4, sort_keys=True)

    def read(self):
        if os.path.isfile(self.path):
            with open(self.path) as f:
                last_config = f.read()
            if last_config:
                self.update(json.loads(last_config))


class SingleInstanceException(Exception):
    def __str__(self):
        return u'已经有另一个实例在运行了'


class SingleInstance(object):
    def __init__(self):
        PID = Config()['PID']
        if isinstance(PID, int) and self.is_pid_exists(PID):
            raise SingleInstanceException
        Config()['PID'] = os.getpid()
        print(Config()['PID'])

    def is_pid_exists(self, pid):
        if sys.platform == 'win32':
            _proc = Popen('TASKLIST /FI "PID eq {}" /FO CSV /NH'.format(pid), stdout=PIPE)
            _stdout = _proc.communicate()[0]
            print(_stdout)
            return '"{}"'.format(pid) in _stdout


class BatchRender(object):
    LOG_FILENAME = u'Nuke批渲染.log'
    LOG_LEVEL = logging.DEBUG

    def __init__(self):
        self.rotate_log()
        self.set_logger()
        self.unlock_files()
        self._queue = multiprocessing.Queue()

        self._config = Config()
        self._error_files = []
        self._files = self.get_files()        

    def run(self):
        self.lock.acquire()
        self.batch_render()
        self.lock.release()

    def continuous_render(self):
        while self.get_files():
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

    @staticmethod
    def get_files():
        _files = list(unicode(i, SYS_CODEC) for i in os.listdir(os.getcwd()) if i.endswith('.nk'))
        _files.sort(key=lambda file: os.path.getmtime(file), reverse=False)

        return _files

    def batch_render(self):
        print(u'将渲染以下文件:')
        for file in self._files:
            print(u'\t\t\t{}'.format(file))
            self._logger.debug (u'发现文件:\t{}'.format(file))
        print(u'总计:\t{}\n'.format(len(self._files)))
        self._logger.debug(u'总计:\t{}'.format(len(self._files)))

        if not self._files:
            self._logger.warning(u'没有找到可渲染文件')
            return False

        self._logger.info('{:-^50s}'.format('<开始批渲染>'))
        for file in self._files:
            _rtcode = self.render(file)

        self._logger.info('<结束批渲染>')

    def render(self, file):
        if not os.path.isfile(file):
            return False

        self._logger.info(u'{}: 开始渲染'.format(file))
        print(u'## [{}/{}]\t{}'.format(self._files.index(file) + 1, len(self._files), file))

        ret = self.call_nuke(file)
        print(u'')

        return ret

    def call_nuke(self, file):
        _time = datetime.datetime.now()
        _file = self.lock_file(file)

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

    def lock_file(self, file):
        locked_file = file + '.lock'
        file_archive_folder = os.path.join('ArchivedRenderFiles', TIME)
        file_archive_dest = os.path.join(file_archive_folder, file)

        shutil.copyfile(file, locked_file)
        print(locked_file)
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
        return locked_file

    def unlock_files(self):
        _locked_file = list(unicode(i, SYS_CODEC) for i in os.listdir(os.getcwd()) if i.endswith('.nk.lock'))
        for f in _locked_file:
            self.unlock_file(f)

    def unlock_file(self, file):
        _unlocked_name = os.path.splitext(file)[0]
        if os.path.isfile(_unlocked_name):
            os.remove(file)
            self._logger.info(u'因为有更新的文件, 移除: {}'.format(file))
        else:
            try:
                os.rename(file, _unlocked_name)
                print(u'解锁: {}'.format(file)) 
                self._logger.info(u'解锁: {}'.format(file))
                return _unlocked_name
            except WindowsError:
                print(u'**错误** 其他程序占用文件: {}'.format(file))
                self._logger.error(u'其他程序占用文件: {}'.format(file))
                self._logger.info(u'<退出>')
                exit()

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

    def hiber(self):
        if self.isHibernate:
            choice = call(u'CHOICE /t 15 /d y /m "即将自动休眠"'.encode(prompt_codec))
            if choice == 2:
                pause()
            else:
                self._logger.info('<计算机进入休眠模式>')
                print('[{}]\t计算机进入休眠模式'.format(time.strftime('%H:%M:%S')))
                call(['SHUTDOWN', '/h'])
        else:
            choice = call(u'CHOICE /t 15 /d y /m "此窗口将自动关闭"'.encode(prompt_codec))
            if choice == 2:
                pause()

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


class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self._config = Config()
        self.setupUi(self)
        self.versionLabel.setText('v{}'.format(VERSION))

        self.edits_key = {  
            self.dirEdit: 'DIR',
        }
        self.change_dir(self._config['DIR'])
        self.update()

        self.connect_actions()
        self.connect_edits()

    def change_dir(self, dir):
        _dir = unicode(os.getcwd(), SYS_CODEC)
        if os.path.isdir(dir) and dir != _dir:
            os.chdir(dir)
            print(u'工作目录改为: {}'.format(dir))
            self.update()

    def connect_actions(self):
        self.actionRender.triggered.connect(self.render)
        self.actionDir.triggered.connect(self.ask_dir)

    def connect_edits(self):
        self.dirEdit.textChanged.connect(lambda dir: self.change_dir(dir))

        for edit, key in self.edits_key.iteritems():
            if isinstance(edit, PySide.QtGui.QLineEdit):
                edit.textChanged.connect(lambda text, k=key: self._config.__setitem__(k, text))
                edit.textChanged.connect(self.update)
            elif isinstance(edit, PySide.QtGui.QCheckBox):
                edit.stateChanged.connect(lambda state, k=key: self._config.__setitem__(k, state))
                edit.stateChanged.connect(self.update)
            elif isinstance(edit, PySide.QtGui.QComboBox):
                edit.currentIndexChanged.connect(lambda index, e=edit, k=key: self._config.__setitem__(k, e.itemText(index)))
            else:
                print(u'待处理的控件: {} {}'.format(type(edit), edit))

    def update(self):
        self.set_edits()
        self.set_list_widget()
        self.set_button_enabled()

    def set_edits(self):
        for q, k in self.edits_key.iteritems():
            try:
                if isinstance(q, PySide.QtGui.QLineEdit):
                    q.setText(self._config[k])
                if isinstance(q, PySide.QtGui.QCheckBox):
                    q.setCheckState(PySide.QtCore.Qt.CheckState(self._config[k]))
            except KeyError as e:
                print(e)

    def set_list_widget(self):
        list = self.listWidget
        list.clear()
        for i in BatchRender.get_files():
            list.addItem(u'{}'.format(i))

    def ask_dir(self):
        _fileDialog = QFileDialog()
        _dir = _fileDialog.getExistingDirectory(dir=os.path.dirname(self._config['DIR']))
        if _dir:
            self._config['DIR'] = _dir
            self.update()

    def render(self):
        self.hide()
        BatchRender().batch_render()
        self.show()

    def set_button_enabled(self):
        self.renderButton.setEnabled(bool(self._config['DIR']))


def main():
    reload(sys)
    sys.setdefaultencoding('UTF-8')
    SingleInstance()
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
        print(e)
        pause()
    except:
        import traceback
        traceback.print_exc()
