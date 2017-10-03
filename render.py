# -*- coding=UTF-8 -*-
"""Task rendering.  """
from __future__ import print_function, unicode_literals

import datetime
import logging
import logging.handlers
import multiprocessing
import multiprocessing.dummy
import os
import re
import shutil
import subprocess
import sys
import time

from config import CONFIG, l10n, stylize
from path import get_unicode, get_encoded
from Qt import QtCore

LOGGER = logging.getLogger('render')


class Queue(list):
    """Task render quene.  """

    def __contains__(self, item):
        if isinstance(item, (str, unicode)):
            return any(i for i in self if i.filename == item)
        return any(i for i in self if i == item)

    def __nonzero__(self):
        return bool(self.enabled_tasks())

    def __str__(self):
        return '[{}]'.format(',\n'.join(str(i) for i in self))

    def __getitem__(self, name):
        if isinstance(name, int):
            return list.__getitem__(self, name)
        elif isinstance(name, (str, unicode)):
            try:
                return [i for i in self if i.filename == name][0]
            except IndexError:
                raise ValueError('No task match filename: %s' % name)
        else:
            raise TypeError('Accept int or str, got %s' % type(name))

    def sort(self):
        list.sort(self, key=lambda x: (x.is_finished, -x.priority, x.mtime))

    def get(self):
        """Get first task from queue.  """
        return self.enabled_tasks()[0]

    def put(self, item):
        """Put task to queue.  """
        if not isinstance(item, Task):
            item = Task(item)
        if item not in self:
            self.append(item)
        self.sort()

    def enabled_tasks(self):
        """All enabled task in queue. """
        self.sort()
        return [i for i in self
                if i.is_enabled and not i.is_doing]


class Task(object):
    """Nuke render task.  """
    filename = None
    is_enabled = True
    is_doing = False
    is_finished = False
    error_count = 0
    priority = 0
    max_retry = 3

    class Clock(object):
        """Caculate remain time.  """
        # TODO
        pass

    def __init__(self, filename, priority=0):
        self.filename = filename
        self.priority = priority
        self.result_files = []
        self.clock = self.Clock()
        self._mtime = os.path.getmtime(self.filename)
        self._proc = None

    def __eq__(self, other):
        return self.filename == other.filename

    def __str__(self):
        return '<Render task:{0.filename}: {0.state}: priority: {0.priority}>'.format(self)

    @property
    def mtime(self):
        """File modified time.  """

        if self.is_doing or not os.path.exists(self.filename):
            return self._mtime

        try:
            mtime = os.path.getmtime(self.filename)
            if mtime != self._mtime:
                LOGGER.debug(
                    'Found mtime change %s -> %s, %s', mtime, self._mtime, self)
                self.is_finished = False
            self._mtime = mtime
        except OSError as ex:
            LOGGER.debug('Update mtime fail %s: %s', self, ex)
        return self._mtime

    @property
    def state(self):
        """The current state as a string.  """
        if self.is_finished:
            return 'finished'
        elif not self.is_enabled:
            return 'disabled'
        elif self.is_doing:
            return 'doing'

        return 'waiting'


class Pool(QtCore.QThread):
    """Single thread render pool.  """
    stdout = QtCore.Signal(unicode)
    stderr = QtCore.Signal(unicode)
    progress = QtCore.Signal(int)
    task_started = QtCore.Signal()
    task_finished = QtCore.Signal()
    queue_started = QtCore.Signal()
    queue_finished = QtCore.Signal()

    def __init__(self, taskqueue):
        super(Pool, self).__init__()
        assert isinstance(taskqueue, Queue)
        self.queue = taskqueue
        self._child_pid = multiprocessing.Value('i')
        self._current_task = multiprocessing.Array('c', 128)
        self.task_started.connect(lambda: self.progress.emit(0))

    @property
    def child_pid(self):
        """Child pid value.  """
        return self._child_pid.value

    @property
    def current_task(self):
        """Current task value.  """
        return get_unicode(self._current_task.value)

    def is_current_task(self, name):
        """Return if @name is current task.  """
        if isinstance(name, Task):
            name = name.filename
        return name[:128] == self.current_task

    def run(self):
        """Overridde.  """
        LOGGER.debug('Render start')
        LOGGER.debug('Task queue:\n %s', self.queue)
        self.queue_started.emit()

        while self.queue:
            LOGGER.debug('Rendering')
            task = self.queue.get()
            try:
                self.execute_task(task)
            except Exception:
                LOGGER.error('Exception during render.', exc_info=True)
                raise
        LOGGER.debug('Render finished.')

        self.queue_finished.emit()
        self.info('渲染结束')

    def info(self, text):
        """Send info to stdout.  """
        self.stdout.emit(stylize(text, 'info'))

    def stop(self):
        """Stop rendering.  """
        pid = self.child_pid
        for task in self.queue:
            task.is_doing = False
        if pid:
            LOGGER.debug('Stoping child: %s', pid)
            try:
                os.kill(pid, 9)
                self.stdout.emit(stylize('终止进程 pid: {}'.format(pid), 'info'))
            except OSError as ex:
                LOGGER.debug('Kill process fail: %s: %s', pid, ex)
        if self.isRunning():
            self.exit(1)
            self.terminate()

    @staticmethod
    def nuke_process(f):
        """Nuke render process for file @f.  """
        f = '"{}"'.format(f.strip('"'))
        nuke = '"{}"'.format(CONFIG['NUKE'].strip('"'))
        args = [nuke,
                '-x',
                '-p' if CONFIG['PROXY'] else '-f',
                '--cont' if CONFIG['CONTINUE'] else '',
                '--priority low' if CONFIG['LOW_PRIORITY'] else '',
                '-c 8G' if CONFIG['LOW_PRIORITY'] else '',
                f]
        args = ' '.join([i for i in args if i])
        if sys.platform != 'win32':
            kwargs = {
                'shell': True
            }
        else:
            kwargs = {}
        LOGGER.debug('Popen: %s', args)
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=CONFIG['DIR'], **kwargs)
        return proc

    def handle_output(self, proc):
        """handle process output."""
        lock = multiprocessing.dummy.Lock()

        def _stderr():
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                line = l10n(line)
                msg = 'STDERR: {}\n'.format(line)
                with lock:
                    sys.stderr.write(msg)
                    with open(CONFIG.log_path, 'a') as f:
                        f.write(msg)
                    self.stderr.emit(stylize(line, 'stderr'))
            LOGGER.debug('Finished thread: handle_stderr')

        def _stdout():
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                match = re.match(r'.*?(\d+)\s?of\s?(\d+)', line)
                if match:
                    percent = int(match.group(1)) * 100 / int(match.group(2))
                    # LOGGER.debug('Percent %s', percent)
                    self.progress.emit(percent)
                line = l10n(line)
                # with lock:
                #     line = l10n(line)
                #     msg = 'STDOUT: {}\n'.format(line)
                #     if LOGGER.getEffectiveLevel() == logging.DEBUG:
                #         sys.stdout.write(msg)
                #     with open(CONFIG.log_path, 'a') as f:
                #         f.write(msg)
                self.stdout.emit(stylize(line, 'stdout'))

            LOGGER.debug('Finished thread: handle_stdout')
        multiprocessing.dummy.Process(
            name='handle_stderr', target=_stderr).start()
        multiprocessing.dummy.Process(
            name='handle_stdout', target=_stdout).start()

    def execute_task(self, task):
        """Render the task file.  """

        assert isinstance(task, Task)

        task.is_doing = True
        self._current_task.value = task.filename
        self.task_started.emit()
        LOGGER.debug('Executing task: %s', task)

        # task.filename = Files.lock(task.filename)
        Files.archive(task.filename)

        time.clock()
        proc = self.nuke_process(task.filename)
        self._child_pid.value = proc.pid
        LOGGER.debug('Started render process: %s', proc.pid)

        self.handle_output(proc)

        retcode = proc.wait()
        LOGGER.info(
            '%s: 结束渲染 耗时 %s %s',
            task.filename,
            timef(time.clock()),
            '退出码: {}'.format(retcode) if retcode else '正常退出',
        )

        if retcode:
            # Exited with error.
            task.error_count += 1
            LOGGER.error('%s: 渲染出错 第%s次', task.filename, task.error_count)
            if task.error_count >= task.max_retry:
                LOGGER.error('%s: 连续渲染错误超过%s次,不再进行重试。',
                             task.max_retry, task.filename)
                task.is_enabled = False
        else:
            # Normal exit.
            if not CONFIG['PROXY']:
                try:
                    mtime = os.path.getmtime(task.filename)
                    if mtime == task.mtime:
                        task.is_finished = True
                        os.remove(task.filename)
                    else:
                        LOGGER.debug(
                            'Found mtime change %s -> %s, will do again %s',
                            mtime, task.mtime, self)
                        task.mtime = mtime
                except OSError:
                    LOGGER.debug('Remove %s fail', task.filename)

        task.is_doing = False
        self.task_finished.emit()
        return retcode


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

    # def unlock_all(self):
    #     """Unlock all .nk.lock files."""

    #     _files = [i for i in self if i.endswith('.nk.lock')]
    #     for f in _files:
    #         self.unlock(f)

    # @staticmethod
    # def unlock(f):
    #     """Rename a (raw_name).(ext) file back or delete it.  """
    #     LOGGER.debug('Unlocking file: %s', f)
    #     if not os.path.exists(f):
    #         LOGGER.warning('尝试解锁不存在的文件: %s', f)
    #         return

    #     _unlocked_name = os.path.splitext(f)[0]
    #     if os.path.isfile(_unlocked_name):
    #         os.remove(f)
    #         LOGGER.info('因为有更新的文件, 移除: %s', f)
    #     else:
    #         LOGGER.debug('%s -> %s', f, _unlocked_name)
    #         os.rename(f, _unlocked_name)
    #     return _unlocked_name

    # @staticmethod
    # def lock(f):
    #     """Duplicate given file with .lock append on name then archive it.  """
    #     LOGGER.debug('Locking file: %s', f)
    #     if f.endswith('.lock'):
    #         return f

    #     Files.archive(f)
    #     locked_file = f + '.lock'
    #     os.rename(f, locked_file)
    #     return locked_file

    @staticmethod
    def archive(f, dest='文件备份'):
        """Archive file in a folder with time struture.  """
        LOGGER.debug('Archiving file: %s -> %s', f, dest)
        now = datetime.datetime.now()
        dest = os.path.join(
            dest,
            get_unicode(now.strftime(
                get_encoded('%y-%m-%d_%A/%H时%M分/'))))

        copy(f, dest)

    def remove_old_version(self):
        """Remove all old version nk files.  """

        LOGGER.info('删除较低版本号文件')
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


def copy(src, dst):
    """Copy src to dst."""
    src, dst = get_unicode(src), get_unicode(dst)
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
