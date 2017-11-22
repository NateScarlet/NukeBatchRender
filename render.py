#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""Task rendering.  """
from __future__ import print_function, unicode_literals

import datetime
import logging
import logging.handlers
import threading
import os
import re
import shutil
import subprocess
import sys
import time

from config import CONFIG, l10n, stylize
from path import get_unicode, get_encoded, version_filter
from Qt import QtCore

LOGGER = logging.getLogger('render')

# Task state bitmask
DOING = 1 << 0
DISABLED = 1 << 1
FINISHED = 1 << 2


class Queue(QtCore.QObject):
    """Task render quene.  """
    changed = QtCore.Signal()

    def __init__(self):
        super(Queue, self).__init__()
        self.clock = Clock(self)
        self.list = []
        self.changed.connect(self.sort)

    def __contains__(self, item):
        if isinstance(item, (str, unicode)):
            return any(i for i in self.list if i.filename == item)
        return any(i for i in self.list if i == item)

    def __nonzero__(self):
        return any(self.enabled_tasks())

    def __len__(self):
        return len(self.list)

    def __str__(self):
        return '[{}]'.format(',\n'.join(str(i) for i in self))

    def __getitem__(self, name):
        if isinstance(name, int):
            return self.list[name]
        elif isinstance(name, (str, unicode)):
            try:
                return [i for i in self if i.filename == name][0]
            except IndexError:
                raise ValueError('No task match filename: %s' % name)
        elif isinstance(name, Task):
            return self.__getitem__(name.filename)
        else:
            raise TypeError('Accept int or str, got %s' % type(name))

    def sort(self):
        """Sort queue.  """

        self.list.sort(key=lambda x: (not x.state & DOING,
                                      x.state, -x.priority, x.mtime))

    def get(self):
        """Get first task from queue.  """

        while True:
            try:
                return self.enabled_tasks().next()
            except StopIteration:
                time.sleep(1)

    def put(self, item):
        """Put task to queue.  """

        if not isinstance(item, Task):
            item = Task(item)
        if item not in self:
            item.queue.add(self)
            self.list.append(item)
            self.changed.emit()
        LOGGER.debug('Add task: %s', item)

    def remove(self, item):
        """Archive file, then remove task and file.  """

        item = self[item]
        assert isinstance(item, Task)
        if item.state & DOING:
            LOGGER.error('不能移除正在进行的任务: %s', item.filename)
            return
        filename = item.filename
        LOGGER.debug('Remove task: %s', item)

        if os.path.exists(filename):
            FILES.remove(filename)
        self.list.remove(item)
        item.queue.discard(self)
        self.changed.emit()

    def enabled_tasks(self):
        """All enabled task in queue. """

        return (i for i in self if not i.state)


class Task(QtCore.QObject):
    """Nuke render task.  """

    filename = None
    state = 0b0
    error_count = 0
    priority = 0
    max_retry = 3
    averge_time = 0.0
    remains_time = 0.0
    frame_count = 0
    clocked_count = 0
    last_time = None
    changed = QtCore.Signal()

    def __init__(self, filename, priority=0):
        super(Task, self).__init__()
        self.filename = filename
        self.priority = priority
        self.queue = set()
        self.result_files = []
        self._mtime = os.path.getmtime(self.filename)
        self._proc = None
        self.changed.connect(self.on_changed)

        # Update timer
        self._timer = QtCore.QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def __eq__(self, other):
        if isinstance(other, Task):
            other = other.filename
        return self.filename == other

    def __str__(self):
        return '<{0.priority}: {0.filename}: {0.state:b}>'.format(self)

    def __setattr__(self, name, value):
        if value is getattr(self, name, None):
            return
        super(Task, self).__setattr__(name, value)
        if name in ('state', 'priority'):
            self.changed.emit()

    def on_changed(self):
        """Send changed signal to queue.  """

        LOGGER.debug('Task changed: %s', self)

        if self.state & DISABLED:
            self._timer.stop()
        else:
            self._timer.start()

        for i in self.queue:
            assert isinstance(i, Queue)
            i.changed.emit()

    def update_mtime(self):
        """Updatge file mtime info.  """

        if os.path.exists(self.filename):
            try:
                old_mtime = self._mtime
                mtime = os.path.getmtime(self.filename)
                self._mtime = mtime

                if mtime != old_mtime:
                    LOGGER.debug(
                        'Found mtime change %s -> %s, %s', old_mtime, mtime, self)
                    self.reset()
                    return True
            except OSError as ex:
                LOGGER.debug('Update mtime fail %s: %s', self, ex)

        return False

    @property
    def mtime(self):
        """File modified time.  """

        if not self.state & DOING:
            self.update_mtime()
        return self._mtime

    @property
    def estimate_time(self):
        """Estimate task time cost.  """

        return self.averge_time * self.frame_count

    def update(self):
        """Update task status.  """

        if not self.state and not os.path.exists(self.filename):
            LOGGER.debug('%s not existed in %s anymore.',
                         self.filename, os.getcwd())
            self.state |= DISABLED
        if not self.state & DOING:
            self.update_mtime()

    def reset(self):
        """Reset this task.  """

        self.state &= DOING
        self.error_count = 0


class Pool(QtCore.QThread):
    """Single thread render pool.  """
    stdout = QtCore.Signal(unicode)
    stderr = QtCore.Signal(unicode)
    progress = QtCore.Signal(int)
    task_started = QtCore.Signal()
    task_finished = QtCore.Signal()
    queue_started = QtCore.Signal()
    queue_finished = QtCore.Signal()
    child_pid = 0
    current_task = None
    stopping = False

    def __init__(self, taskqueue):
        super(Pool, self).__init__()
        assert isinstance(taskqueue, Queue)
        self.queue = taskqueue
        self.task_started.connect(lambda: self.progress.emit(0))

    def is_current_task(self, name):
        """Return if @name is current task.  """
        if isinstance(name, Task):
            name = name.filename
        return name == self.current_task

    def run(self):
        """Overridde.  """
        LOGGER.debug('Render start')
        self.queue_started.emit()

        while not self.stopping and self.queue:
            LOGGER.debug('Rendering queue:\n%s', self.queue)
            task = self.queue.get()
            try:
                self.execute_task(task)
            except Exception:
                LOGGER.error('Exception during render.', exc_info=True)
                self.stop()
                raise
        LOGGER.debug('Render finished:\n%s', self.queue)

        self.queue_finished.emit()
        self.info('渲染结束')

    def info(self, text):
        """Send info to stdout.  """

        LOGGER.info(text)
        self.stdout.emit(stylize(text, 'info'))

    def error(self, text):
        """Send error to stderr.  """

        LOGGER.error(text)
        self.stderr.emit(stylize(text, 'error'))

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        pid = self.child_pid
        for task in self.queue:
            task.state &= ~DOING
        if pid:
            LOGGER.debug('Stoping child: %s', pid)
            try:
                os.kill(pid, 9)
            except OSError as ex:
                LOGGER.debug('Kill process fail: %s: %s', pid, ex)
        if self.isRunning():
            self.exit(1)
        self.wait()

    @staticmethod
    def nuke_process(f):
        """Nuke render process for file @f.  """
        f = '"{}"'.format(f.strip('"'))
        nuke = '"{}"'.format(CONFIG['NUKE'].strip('"'))
        _memory_limit = CONFIG['MEMORY_LIMIT']
        args = [nuke,
                '-x',
                '-p' if CONFIG['PROXY'] else '-f',
                '--cont' if CONFIG['CONTINUE'] else '',
                '--priority low' if CONFIG['LOW_PRIORITY'] else '',
                '-c {}M'.format(
                    int(_memory_limit * 1024)) if _memory_limit and CONFIG['LOW_PRIORITY'] else '',
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

        def _stderr():
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                line = l10n(line)
                msg = 'STDERR: {}\n'.format(line)
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
                    total = int(match.group(2))
                    percent = int(match.group(1)) * 100 / total
                    # LOGGER.debug('Percent %s', percent)
                    self.progress.emit(percent)
                    self.current_task.frame_count = total
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
        threading.Thread(name='handle_stderr', target=_stderr).start()
        threading.Thread(name='handle_stdout', target=_stdout).start()

    def execute_task(self, task):
        """Render the task file.  """

        assert isinstance(task, Task)

        task.state |= DOING
        self.current_task = task
        self.task_started.emit()
        self.info('执行任务: {0.filename} 优先级:{0.priority}'.format(task))

        # task.filename = Files.lock(task.filename)
        Files.archive(task.filename)

        task.update_mtime()
        start_time = time.clock()
        proc = self.nuke_process(task.filename)
        self.child_pid = proc.pid
        self.info('开始进程 pid: {}'.format(proc.pid))

        self.handle_output(proc)

        retcode = proc.wait()
        time_cost = timef(time.clock() - start_time)
        retcode_str = '退出码: {}'.format(retcode) if retcode else '正常退出'
        self.info('{}: 结束渲染 耗时 {} {}'.format(
            task.filename, time_cost, retcode_str))

        if self.stopping:
            # Stopped by user.
            self.info('中途终止进程 pid: {}'.format(proc.pid))
        elif retcode:
            # Exited with error.
            task.error_count += 1
            task.priority -= 1
            self.error('{}: 渲染出错 第{}次'.format(task.filename, task.error_count))
            if task.error_count >= task.max_retry:
                self.error('渲染错误达到{}次,不再进行重试。'.format(task.max_retry))
                task.state |= DISABLED
        else:
            # Normal exit.
            if task.update_mtime():
                self.info('发现修改日期变更, 将再次执行任务 {}'.format(task))
            elif CONFIG['PROXY']:
                task.state |= DISABLED
            else:
                task.state |= FINISHED
                self.info('任务完成')
                try:
                    Files.remove(task.filename)
                except OSError:
                    self.error('移除文件 {} 失败'.format(task.filename))

        task.state &= ~DOING
        self.task_finished.emit()
        return retcode


class Clock(QtCore.QObject):
    """Caculate remain time for a queue.  """
    averge_time = 0.0
    clocked_count = 0
    _averge_frame_count = 0
    remains_changed = QtCore.Signal(float)

    def __init__(self, queue):
        super(Clock, self).__init__()
        assert isinstance(queue, Queue)
        self.queue = queue
        self.time_out_timer = QtCore.QTimer()
        self.time_out_timer.setSingleShot(True)
        self.time_out = self.time_out_timer.timeout

    def start_clock(self, pool):
        """Start record time information for @pool.  """

        assert isinstance(pool, Pool)
        pool.progress.connect(
            lambda value: self.record(pool.current_task, value))

    @property
    def averge_frame_count(self):
        """Predicted averge frame count.  """

        counts = [i.frame_count for i in self.queue]
        counts = [i for i in counts if i]
        if counts:
            return reduce(int.__add__, counts) / len(counts)
        return 100

    def record(self, task, value):
        """Record time information.  """

        assert isinstance(task, Task)
        if value == 0:
            task.last_time = time.clock()
            return

        if task.last_time is not None:
            frame_time = time.clock() - task.last_time
            total_time = task.averge_time * task.clocked_count + frame_time
            self_total_time = self.averge_time * self.clocked_count + frame_time
            task.clocked_count += 1
            self.clocked_count += 1
            task.averge_time = total_time / task.clocked_count
            self.averge_time = self_total_time / self.clocked_count
            task.remains_time = task.estimate_time * (100 - value) / 100
            # LOGGER.debug('task %s remains %s', task, task.remains_time)
        task.last_time = time.clock()

        self.remains_changed.emit(self.remains())

        self.time_out_timer.stop()
        if CONFIG['TIME_OUT']:
            self.time_out_timer.start(CONFIG['TIME_OUT'] * 1000)

    def remains(self):
        """This render remains time.  """

        ret = 0
        for i in [i for i in self.queue if not i.state & (DISABLED | FINISHED)]:
            if i.state & DOING:
                ret += i.remains_time
            else:
                ret += i.estimate_time or self.averge_time * \
                    (i.frame_count or self.averge_frame_count)

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
        ret += '{:.0f}小时'.format(hour)
    if minute:
        ret += '{:.0f}分'.format(minute)
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

    def old_version_files(self):
        """Files that already has higher version.  """

        newest = version_filter(self)
        ret = [i for i in self if i not in newest]
        return ret

    @classmethod
    def remove(cls, f):
        """Archive file then remove it.  """

        cls.archive(f)
        if not os.path.isabs(f):
            os.remove(get_encoded(f))

    @staticmethod
    def split_version(f):
        """Return nuke style _v# (shot, version number) pair.

        >>> Files.split_version('sc_001_v20.nk')
        (u'sc_001', 20)
        >>> Files.split_version('hello world')
        (u'hello world', None)
        >>> Files.split_version('sc_001_v-1.nk')
        (u'sc_001_v-1', None)
        >>> Files.split_version('sc001V1.jpg')
        (u'sc001', 1)
        >>> Files.split_version('sc001V1_no_bg.jpg')
        (u'sc001', 1)
        >>> Files.split_version('suv2005_v2_m.jpg')
        (u'suv2005', 2)
        """

        f = os.path.splitext(f)[0]
        match = re.match(r'(.+)v(\d+)', f, flags=re.I)
        if not match:
            return (f, None)
        shot, version = match.groups()
        return (shot.rstrip('_'), int(version))


FILES = Files()


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
