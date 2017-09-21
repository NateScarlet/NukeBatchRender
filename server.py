# -*- coding=UTF-8 -*-
"""Batch render server."""
import os
import sys
import time
import datetime
import json
import logging
import shutil
import re
from subprocess import Popen, PIPE, call
import multiprocessing
import multiprocessing.dummy
from multiprocessing.connection import Listener

import singleton
from path import get_unicode

ADDRESS = ('localhost', 55666)
AUTH_KEY = b'NukeBatchRender'
LOGGER = logging.getLogger('NukeBatchRender')

__version__ = '0.1.0'


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
        LOGGER.debug(key, value)
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


class Command(object):
    """Command for this server.  """
    message_type = 'NukeBatchRender.Command'

    def __init__(self, name, *args, **kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return '{0.name}(args={0.args}, kwargs={0.kwargs})'.format(self)

    def execute(self):
        """Execute this command.  """
        quene = multiprocessing.Queue(maxsize=1)

        def _func():
            LOGGER.debug('Execute %s', self)
            try:
                ret = getattr(Server, self.name)(*self.args, **self.kwargs)
                quene.put(ret)
            except AttributeError:
                LOGGER.error('Not found command %s', self)
            except Exception as ex:
                LOGGER.error('Exception %s \nwhen running %s', ex, self)
                raise
        proc = multiprocessing.dummy.Process(target=_func, name=str(self))
        proc.start()
        proc.join()
        if not quene.empty():
            return quene.get()


def main():
    """Script entry.  """
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)5s: %(message)s', '%x %X')
    _handler.setFormatter(_formatter)
    LOGGER.addHandler(_handler)
    # LOGGER.setLevel(logging.INFO)
    LOGGER.setLevel(logging.DEBUG)

    print(u'Nuke批渲染 服务端 {}'.format(__version__))

    server = Server()
    server.listen()


class Server(object):
    """BatchRender Server.  """
    jobs = []
    instance = None
    config = Config()
    CLOSE = 'CLOSE'

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Server, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self._listener = Listener(ADDRESS, authkey=AUTH_KEY)

    def __del__(self):
        self._listener.close()

    def listen(self):
        """Listen client.  """
        while True:
            LOGGER.debug('Accepting...')
            conn = self._listener.accept()
            LOGGER.debug(u'Accept from: %s', self._listener.last_accepted)

            while True:
                ret = None
                msg = conn.recv()
                LOGGER.debug('>>> %s', msg)

                if msg == self.CLOSE:
                    LOGGER.debug(u'Close: %s', self._listener.last_accepted)
                    conn.close()
                    break
                elif msg == 'SHUTDOWN':
                    conn.send(self.CLOSE)
                    LOGGER.info(u'关闭')
                    pause()
                    sys.exit()
                elif hasattr(msg, 'message_type'):
                    ret = self.handle_message(msg)

                conn.send(ret)

    def handle_message(self, msg):
        if msg.message_type == Command.message_type:
            return msg.execute()

    @staticmethod
    def get_config():
        return Server.config

    @staticmethod
    def hiber():
        """Hibernate this computer.  """

        proc = Popen('SHUTDOWN /H', stderr=PIPE)
        stderr = get_unicode(proc.communicate()[1])
        print(stderr)
        if u'没有启用休眠' in stderr:
            print(u'转为使用关机')
            call('SHUTDOWN /S')

    @staticmethod
    def set_dir(value):
        """Set working dir.  """
        os.chdir(value)
        LOGGER.info(u'目录变更为 {}'.format(value))
        return 'haha'

    @staticmethod
    def render(self):
        """Start rendering from UI.  """

        _file = os.path.abspath(os.path.join(__file__, '../error_handler.exe'))
        Popen(_file)
        self._proc = BatchRender()
        self._proc.start()

    @staticmethod
    def stop():
        pass

    @staticmethod
    def is_rendering(self):
        # TODO
        # self.statusbar.showMessage(u'渲染中')
        pass


def copy(src, dst):
    """Copy src to dst."""
    LOGGER.info(u'%s -> %s', src, dst)
    if not os.path.exists(src):
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    shutil.copy2(src, dst)


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
        _proc = Popen(get_unicode(cmd), stderr=PIPE)
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
            except OSError as ex:
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


def start():
    """Start server process.  """
    Popen('"{}" "{}"'.format(sys.executable, __file__))


def pause():
    """Pause prompt with a countdown."""

    print(u'')
    for i in range(5)[::-1]:
        sys.stdout.write(u'\r{:2d}'.format(i + 1))
        time.sleep(1)
    sys.stdout.write(u'\r          ')
    print(u'')


if __name__ == '__main__':
    SINGLETON = singleton.SingleInstance(on_exit=pause)
    main()
