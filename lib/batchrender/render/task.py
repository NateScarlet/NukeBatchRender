# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import os

import re
import sys
import threading
import time
from subprocess import Popen, PIPE

from Qt.QtCore import Signal

from ..config import CONFIG, l10n, stylize
# from ..files import FILES
from .. import database
from .. import model
from . import core
LOGGER = logging.getLogger(__name__)


class Task(core.RenderObject):
    """Nuke render task.  """

    frame_finished = Signal(dict)
    file_changed = Signal(dict)
    max_retry = 3

    def __init__(self, path, queue, session=database.SESSION):
        from .queue import Queue
        assert isinstance(queue, Queue), type(queue)
        super(Task, self).__init__()

        self.file = database.File.from_path(path, session)
        self.queue = queue
        self.label = self.file.label
        self.session = session
        self.error_count = 0
        self.proc = None
        self.frames = None

        self.frame_finished.connect(self.on_frame_finished)
        self.file_changed.connect(self.on_file_changed)
        self.stdout.connect(self.queue.stdout)
        self.stderr.connect(self.queue.stderr)

    def __eq__(self, other):
        if isinstance(other, Task):
            other = other.file.path
        return self.file.path == other

    def __str__(self):
        return '<{0.priority}: {0.label}: {0.state:b}>'.format(self)

    def __unicode__(self):
        return '<任务 {0.label}: 优先级 {0.priority}, 状态 {0.state:b}>'.format(self)

    @property
    def state(self):
        """Task state.  """

        return self._get_model_data(model.ROLE_STATUS)

    @property
    def range(self):
        """Render range.  """

        return self._get_model_data(model.ROLE_RANGE)

    @property
    def priority(self):
        """Task priority.  """

        return self._get_model_data(model.ROLE_PRIORITY)

    @property
    def estimate_time(self):
        """Estimate task time cost.  """

        return self.file.estimate_cost(self.frames)

    @state.setter
    def state(self, value):

        if value != self.state:
            self._set_model_data(value, model.ROLE_STATUS)

    @priority.setter
    def priority(self, value):
        if value != self._priority:
            self._set_model_data(value, model.ROLE_PRIORITY)

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        self.state &= ~model.DOING
        proc = self.proc
        if proc is not None:
            assert isinstance(proc, Popen)
            proc.terminate()
            proc.wait()

    def reset(self):
        """Reset this task.  """

        self.state &= model.DOING
        self.error_count = 0

    def handle_output(self, proc):
        """handle process output."""

        self._handle_stderr(proc)
        self._handle_stdout(proc)

    def run(self):
        """(Override)"""

        start_time = time.clock()
        self.state |= model.DOING

        temp = self.file.create_tempfile()
        proc = nuke_process(temp, self.range)
        self.proc = proc
        self.handle_output(proc)

        self.info(
            '执行任务: {0.file.path} 优先级:{0.priority} pid: {1}'.format(self, proc.pid))
        self.started.emit()

        retcode = proc.wait()
        time_cost = core.timef(time.clock() - start_time)
        retcode_str = '退出码: {}'.format(retcode) if retcode else '正常退出'
        self.info('{}: 结束渲染 耗时 {} {}'.format(
            self.file.path, time_cost, retcode_str))

        if self.stopping:
            # Stopped by user.
            self.info('中途终止进程 pid: {}'.format(proc.pid))
            self.stopping = False
        elif retcode:
            # Exited with error.
            self.error_count += 1
            self.priority -= 1
            self.error('{}: 渲染出错 第{}次'.format(
                self.file.path, self.error_count))
            if self.error_count >= self.max_retry:
                self.error('渲染错误达到{}次,不再进行重试。'.format(self.max_retry))
                self.state |= model.DISABLED
        else:
            # Normal exit.
            if CONFIG['PROXY']:
                self.state |= model.DISABLED
            else:
                self.state |= model.FINISHED
                self.info('任务完成')
                self.file.archive()
        try:
            os.remove(temp)
        except OSError:
            self.error('移除临时文件失败: {}'.format(temp))
            LOGGER.warning('Remove temprory file failed.', exc_info=True)

        self.state &= ~model.DOING
        self.finished.emit()
        return retcode

    def on_frame_finished(self, **kwargs):
        frame, cost, current, total = (kwargs['frame'],
                                       kwargs['cost'],
                                       kwargs['current'],
                                       kwargs['total'])
        if current == 1:
            fisrt_frame = frame
            last_frame = fisrt_frame + total - 1
            self.frames = total
            self._update_file_range(frame, last_frame)

        frame_record = database.Frame(file=self.file, frame=frame, cost=cost)
        database.SESSION.add(frame_record)
        database.SESSION.commit()
        self.progressed.emit(current * 100 / total)
        self.changed.emit()

    def on_changed(self):
        """Send changed signal to queue.  """

        LOGGER.debug('Task changed: %s', self)

        self.queue.changed.emit()

    def on_progressed(self, value):
        self._remains = (100 - value) * self.estimate_time / 100.0

    def on_file_changed(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self.file, k, v)
        self.session.commit()

    def _get_model_data(self, role):
        model_ = self.queue.model.sourceModel()
        index = model_.index(self.file.path.as_posix())
        return model_.data(index, role)

    def _set_model_data(self, value, role):
        model_ = self.queue.model.sourceModel()
        index = model_.index(self.file.path.as_posix())
        model_.setData(index, value, role)

    def _update_file_range(self, fisrt_frame, last_frame):
        old_fisrt, old_last = self.file.fisrt_frame, self.file.last_frame
        if old_fisrt is not None:
            fisrt_frame = min(fisrt_frame, old_fisrt)
        if old_last is not None:
            last_frame = max(last_frame, old_last)

        self.file.fisrt_frame = fisrt_frame
        self.file.last_frame = last_frame

    @core.run_async
    def _handle_stderr(self, proc):
        while self.state & model.DOING:
            line = proc.stderr.readline()
            if not line:
                break
            line = l10n(line)
            msg = 'STDERR: {}\n'.format(line)
            with open(CONFIG.log_path, 'a') as f:
                f.write(msg)
            self.stderr.emit(stylize(line, 'stderr'))
        LOGGER.debug('Finished thread: handle_stderr')

    @core.run_async
    def _handle_stdout(self, proc, **context):
        start_time = time.clock()
        context['last_frame_time'] = start_time

        while self.state & model.DOING:
            line = proc.stdout.readline()
            if not line:
                break

            self._match_stdout(line, context)

            self.stdout.emit(stylize(l10n(line), 'stdout'))

        if not self.stopping:
            self.file_changed.emit({'last_finish_time': time.time(),
                                    'last_cost': time.clock() - start_time})
        LOGGER.debug('Finished thread: handle_stdout')

    def _match_stdout(self, line, context, **data):
        match = re.match(r'Frame (\d+) \((\d+) of (\d+)\)', line)

        if match:
            now = time.clock()

            data['frame'] = int(match.group(1))
            data['current'] = int(match.group(2))
            data['total'] = int(match.group(3))
            data['cost'] = now - context['last_frame_time']

            self.frame_finished.emit(data)
            context['last_frame_time'] = now


def nuke_process(f, range_):
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
            if _memory_limit
            else '',
            '-m {}'.format(CONFIG['THREADS']),
            f, range_]
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
