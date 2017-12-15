#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import os

import re
import sys
import threading
import time
from functools import wraps
from subprocess import Popen, PIPE
from abc import abstractmethod

from Qt.QtCore import QObject, QTimer, Signal

from config import CONFIG, l10n, stylize
from files import FILES
from database import DATABASE


LOGGER = logging.getLogger('render')


# Task state bitmask
DOING = 1 << 0
DISABLED = 1 << 1
FINISHED = 1 << 2


def run_async(func):
    """Run func in thread.  """

    @wraps(func)
    def _func(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return _func


class RenderObject(QObject):
    """Base render object.  """

    stopping = False
    _remains = None

    # Signals.
    changed = Signal()
    started = Signal()
    stopped = Signal()
    finished = Signal()
    time_out = Signal()
    progressed = Signal(int)
    stdout = Signal(str)
    stderr = Signal(str)

    def __init__(self):
        super(RenderObject, self).__init__()

        # Singals.
        self.changed.connect(self.on_changed)
        self.progressed.connect(self.on_progressed)
        self.time_out.connect(self.on_time_out)
        self.started.connect(lambda: self.progressed.emit(0))
        self.stopped.connect(self.on_stopped)
        self.finished.connect(self.on_finished)
        self.stdout.connect(self.on_stdout)
        self.stderr.connect(self.on_stderr)

    def info(self, text):
        """Send info to stdout.  """

        LOGGER.info('%s: %s', self, text)
        self.stdout.emit(stylize(text, 'info'))

    def error(self, text):
        """Send error to stderr.  """

        LOGGER.error('%s: %s', self, text)
        self.stderr.emit(stylize(text, 'error'))

    @property
    def remains(self):
        """Time remains of this.  """

        return self._remains

    @abstractmethod
    def on_changed(self):
        pass

    @abstractmethod
    def on_stopped(self):
        pass

    @abstractmethod
    def on_finished(self):
        pass

    @abstractmethod
    def on_time_out(self):
        pass

    @abstractmethod
    def on_progressed(self, value):
        pass

    @abstractmethod
    def on_stdout(self, msg):
        pass

    @abstractmethod
    def on_stderr(self, msg):
        pass


class Queue(RenderObject):
    """Task render quene.  """

    def __init__(self):
        super(Queue, self).__init__()
        self._list = []
        self.changed.connect(self.sort)

    def __contains__(self, item):
        if isinstance(item, (str, unicode)):
            return any(i for i in self if i.filename == item)
        return any(i for i in self if i == item)

    def __nonzero__(self):
        return any(self.enabled_tasks())

    def __len__(self):
        return self._list.__len__()

    def __str__(self):
        return '[{}]'.format(',\n'.join(str(i) for i in self._list))

    def __getitem__(self, name):
        if isinstance(name, int):
            return self._list.__getitem__(name)
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

        self._list.sort(key=lambda x: (not x.state & DOING,
                                       x.state, -x.priority, x.mtime))

    def get(self):
        """Get first task from queue.  """

        try:
            return self.enabled_tasks().next()
        except StopIteration:
            time.sleep(1)
            return self.get()

    def put(self, item):
        """Put task to queue.  """

        if item in self:
            self[item].update()
            return
        elif not isinstance(item, Task):
            item = Task(item)
        item.queue.add(self)
        self._list.append(item)
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
        self._list.remove(item)
        item.queue.discard(self)
        self.changed.emit()

    def enabled_tasks(self):
        """All enabled task in queue. """

        self.sort()
        return (i for i in self if not i.state)

    @property
    def remains(self):
        ret = 0
        for i in list(i for i in self if not i.state or i.state & DOING):
            assert isinstance(i, Task)
            if i.state & DOING:
                ret += (i.remains
                        or i.estimate_time)
            else:
                ret += i.estimate_time

        return ret

    def on_changed(self):
        self.sort()


class Task(RenderObject):
    """Nuke render task.  """

    _priority = 0
    _state = 0b0
    filename = None
    error_count = 0
    max_retry = 3
    mtime = None
    proc = None
    updating = False

    def __init__(self, filename):
        super(Task, self).__init__()

        self.filename = filename
        self.frames = DATABASE.get_task_frames(filename)
        self.queue = set()
        self.update_mtime()

        # Update timer.
        timer = QTimer()
        timer.setInterval(1000)
        timer.timeout.connect(self.update)
        timer.start()
        self._update_timer = timer

    def __eq__(self, other):
        if isinstance(other, Task):
            other = other.filename
        return self.filename == other

    def __str__(self):
        return '<{0.priority}: {0.filename}: {0.state:b}>'.format(self)

    def __unicode(self):
        return '<任务 {0.filename}: 优先级 {0.priority}, 状态 {0.state:b}>'.format(self)

    def on_changed(self):
        """Send changed signal to queue.  """

        LOGGER.debug('Task changed: %s', self)

        for i in self.queue:
            assert isinstance(i, Queue)
            i.changed.emit()

    def on_progressed(self, value):
        self._remains = (100 - value) * self.estimate_time / 100.0

    def on_stdout(self, msg):
        for i in self.queue:
            i.stdout.emit(msg)

    def on_stderr(self, msg):
        for i in self.queue:
            i.stderr.emit(msg)

    def update_mtime(self):
        """Updatge file mtime info.  """

        if os.path.exists(self.filename):
            try:
                old = self.mtime
                current = os.path.getmtime(self.filename)
                self.mtime = current

                if old and current != old:
                    LOGGER.debug(
                        'Found mtime change %s -> %s, %s', old, current, self)
                    self.reset()
                    return True
            except OSError as ex:
                LOGGER.debug('Update mtime fail %s: %s', self, ex)

        return False

    @property
    def state(self):
        """Task state.  """

        return self._state

    @state.setter
    def state(self, value):
        if value != self._state:
            if value & DISABLED:
                self._update_timer.stop()
            else:
                self._update_timer.start()
            self._state = value
            self.changed.emit()

    @property
    def priority(self):
        """Task priority.  """

        return self._priority

    @priority.setter
    def priority(self, value):
        if value != self._priority:
            self._priority = value
            LOGGER.debug(value)
            self.changed.emit()

    @property
    def estimate_time(self):
        """Estimate task time cost.  """

        return (DATABASE.get_task_cost(self.filename)
                or DATABASE.averge_task_cost)

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        self.state &= ~DOING
        proc = self.proc
        if proc is not None:
            assert isinstance(proc, Popen)
            proc.terminate()
            proc.wait()

    def update(self):
        """Update task status.  """

        if self.updating:
            return

        self.updating = True

        if not self.state and not os.path.exists(self.filename):
            LOGGER.debug('%s not existed in %s anymore.',
                         self.filename, os.getcwd())
            self.state |= DISABLED
        if not self.state & DOING:
            self.update_mtime()

        self.updating = False

    def reset(self):
        """Reset this task.  """

        self.state &= DOING
        self.error_count = 0

    def handle_output(self, proc):
        """handle process output."""

        def _stderr():
            while self.state & DOING:
                line = proc.stderr.readline()
                if not line:
                    break
                line = l10n(line)
                msg = 'STDERR: {}\n'.format(line)
                with open(CONFIG.log_path, 'a') as f:
                    f.write(msg)
                self.stderr.emit(stylize(line, 'stderr'))
            LOGGER.debug('Finished thread: handle_stderr')

        def _stdout():
            start_time = time.clock()
            last_frame_time = start_time

            while self.state & DOING:
                line = proc.stdout.readline()
                if not line:
                    break
                match = re.match(r'.*?(\d+)\s?of\s?(\d+)', line)

                # Record rendering time.
                if match:
                    now = time.clock()
                    total = int(match.group(2))
                    current = int(match.group(1))
                    cost = now - last_frame_time
                    last_frame_time = now

                    DATABASE.set_frame_time(self.filename, current, cost)
                    if self.frames != total:
                        self.frames = total
                        DATABASE.set_task(self.filename, total)
                        self.changed.emit()
                    self.progressed.emit(current * 100 / total)

                line = l10n(line)
                self.stdout.emit(stylize(line, 'stdout'))

            if not self.stopping:
                DATABASE.set_task(self.filename, self.frames,
                                  time.clock() - start_time)
            LOGGER.debug('Finished thread: handle_stdout')

        threading.Thread(name='handle_stderr', target=_stderr).start()
        threading.Thread(name='handle_stdout', target=_stdout).start()

    def run(self):
        """(Override)"""

        def nuke_process(f):
            """Nuke render process for file @f.  """

            # return subprocess.Popen('cmd /c echo 1',
            #  stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            f = '"{}"'.format(f.strip('"'))
            nuke = '"{}"'.format(CONFIG['NUKE'].strip('"'))
            _memory_limit = CONFIG['MEMORY_LIMIT']
            args = [nuke,
                    '-x',
                    '-p' if CONFIG['PROXY'] else '-f',
                    '--cont' if CONFIG['CONTINUE'] else '',
                    '--priority low' if CONFIG['LOW_PRIORITY'] else '',
                    '-c {}M'.format(int(_memory_limit * 1024))
                    if _memory_limit and CONFIG['LOW_PRIORITY']
                    else '',
                    f]
            args = ' '.join([i for i in args if i])
            if sys.platform != 'win32':
                kwargs = {
                    'shell': True
                }
            else:
                kwargs = {}
            LOGGER.debug('Popen: %s', args)
            proc = Popen(args, stdout=PIPE, stderr=PIPE,
                         cwd=CONFIG['DIR'], **kwargs)
            return proc

        self.update_mtime()
        start_time = time.clock()
        self.state |= DOING

        FILES.archive(self.filename)
        proc = nuke_process(self.filename)
        self.proc = proc
        self.handle_output(proc)

        self.info(
            '执行任务: {0.filename} 优先级:{0.priority} pid: {1}'.format(self, proc.pid))
        self.started.emit()

        retcode = proc.wait()
        time_cost = timef(time.clock() - start_time)
        retcode_str = '退出码: {}'.format(retcode) if retcode else '正常退出'
        self.info('{}: 结束渲染 耗时 {} {}'.format(
            self.filename, time_cost, retcode_str))

        if self.stopping:
            # Stopped by user.
            self.info('中途终止进程 pid: {}'.format(proc.pid))
            self.stopping = False
        elif retcode:
            # Exited with error.
            self.error_count += 1
            self.priority -= 1
            self.error('{}: 渲染出错 第{}次'.format(self.filename, self.error_count))
            if self.error_count >= self.max_retry:
                self.error('渲染错误达到{}次,不再进行重试。'.format(self.max_retry))
                self.state |= DISABLED
        else:
            # Normal exit.
            if self.update_mtime():
                self.info('发现修改日期变更, 将再次执行任务。')
            elif CONFIG['PROXY']:
                self.state |= DISABLED
            else:
                self.state |= FINISHED
                self.info('任务完成')
                try:
                    FILES.remove(self.filename)
                except OSError:
                    self.error('移除文件 {} 失败'.format(self.filename))

        self.state &= ~DOING
        self.finished.emit()
        return retcode


class Slave(RenderObject):
    """Render slave.  """

    _task = None
    rendering = False

    def __init__(self):
        super(Slave, self).__init__()

        # Time out timer.
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self.time_out)
        self._time_out_timer = timer

    @property
    def task(self):
        """Current render task.  """

        return self._task

    @task.setter
    def task(self, value):
        assert value is None or isinstance(value, Task), value

        old = self._task
        if isinstance(old, Task):
            old.progressed.disconnect(self.progressed)
        if isinstance(value, Task):
            value.progressed.connect(self.progressed)
        self._task = value

    @run_async
    def start(self, queue):
        """Overridde.  """

        if self.rendering or self.stopping:
            return

        self.rendering = True

        LOGGER.debug('Render start')
        self.started.emit()

        while queue and not self.stopping:
            LOGGER.debug('Rendering queue:\n%s', queue)
            try:
                task = queue.get()
                assert isinstance(task, Task)
                self.task = task
                task.run()
            except Exception:
                LOGGER.error('Exception during render.', exc_info=True)
                raise

        if not self.stopping:
            self.finished.emit()
        self.stopped.emit()

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        task = self.task
        if isinstance(task, Task):
            task.stop()

    def on_stopped(self):
        LOGGER.debug('Render stopped.')
        self._time_out_timer.stop()
        self.rendering = False
        self.stopping = False
        self.task = None

    def on_finished(self):
        LOGGER.debug('Render finished.')

    def on_time_out(self):
        task = self.task
        self.error(u'{}: 渲染超时'.format(task))
        if isinstance(task, Task):
            task.priority -= 1
            task.stop()

    def on_progressed(self, value):
        if CONFIG['LOW_PRIORITY']:
            # Restart timeout timer.
            timer = self._time_out_timer
            time_out = CONFIG['TIME_OUT'] * 1000

            timer.stop()
            if time_out > 0:
                timer.start(time_out)


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
