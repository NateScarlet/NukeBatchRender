# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import os

import re
import sys
import threading
import time
from subprocess import Popen, PIPE

from Qt.QtCore import QTimer

from ..config import CONFIG, l10n, stylize
from ..files import FILES
from ..database import DATABASE

from . import core
LOGGER = logging.getLogger(__name__)


class Task(core.RenderObject):
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
            from .queue import Queue
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
            if value & core.DISABLED:
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

        return (DATABASE.get_averge_time(self.filename) * self.frames
                if self.frames and self.state & core.DOING
                else DATABASE.get_task_cost(self.filename)
                or DATABASE.averge_task_cost)

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        self.state &= ~core.DOING
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
            LOGGER.debug('%s not existed anymore.', self.filename)
            self.state |= core.DISABLED
        if not self.state & core.DOING:
            self.update_mtime()

        self.updating = False

    def reset(self):
        """Reset this task.  """

        self.state &= core.DOING
        self.error_count = 0

    def handle_output(self, proc):
        """handle process output."""

        def _stderr():
            while self.state & core.DOING:
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

            while self.state & core.DOING:
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
        self.state |= core.DOING

        FILES.archive(self.filename)
        proc = nuke_process(self.filename)
        self.proc = proc
        self.handle_output(proc)

        self.info(
            '执行任务: {0.filename} 优先级:{0.priority} pid: {1}'.format(self, proc.pid))
        self.started.emit()

        retcode = proc.wait()
        time_cost = core.timef(time.clock() - start_time)
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
                self.state |= core.DISABLED
        else:
            # Normal exit.
            if self.update_mtime():
                self.info('发现修改日期变更, 将再次执行任务。')
            elif CONFIG['PROXY']:
                self.state |= core.DISABLED
            else:
                self.state |= core.FINISHED
                self.info('任务完成')
                try:
                    FILES.remove(self.filename)
                except OSError:
                    self.error('移除文件 {} 失败'.format(self.filename))

        self.state &= ~core.DOING
        self.finished.emit()
        return retcode
