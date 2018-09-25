# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import sys
import time
from subprocess import PIPE, Popen

import pendulum
from Qt.QtCore import Signal

from . import core
from .. import database, model, texttools
from ..codectools import get_encoded as e
from ..codectools import get_unicode as u
from ..config import CONFIG
from ..exceptions import AlreadyRendering
from ..threadtools import run_async
from .proc_handler import NukeHandler

LOGGER = logging.getLogger(__name__)


class NukeTask(model.Task, core.RenderObject):
    """Nuke render task.  """

    min_progress_interval = 1
    min_timestamp_interval = 5
    frame_finished = Signal(dict)
    process_finished = Signal(int)

    max_retry = 3

    def __init__(self, index, dir_model):
        super(NukeTask, self).__init__(index, dir_model)

        self._tempfile = None
        self._filehash = None
        self.proc = None
        self.start_time = None
        self.last_progress_time = None
        self._last_timestamp_time = None
        self._frames_records = []
        self._output_records = []
        self._last_commit_time = None

        self.frame_finished.connect(self.on_frame_finished)
        self.process_finished.connect(self.on_process_finished)

    def __eq__(self, other):
        if isinstance(other, model.Task):
            other = other.path
        return self.path == other

    def abort(self):
        """Abort rendering.  """

        self.is_aborting = True
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

        handler = NukeHandler(proc)
        handler.stdout.connect(self.stdout)
        handler.stderr.connect(self.stderr)
        handler.frame_finished.connect(self.frame_finished)
        handler.output_updated.connect(self.on_output_updated)
        handler.start()

    def start(self):
        """Start rendering.  """

        self.start_time = time.time()
        self.is_aborting = False

        with database.util.session_scope() as sess:
            self.update_file(sess)
            if self.file.is_rendering():
                raise AlreadyRendering
            self._tempfile = self.file.create_tempfile()
            self._filehash = self.file.hash

        self.start_process()
        self.started.emit()

    @run_async
    def start_process(self):
        """Start render process.  """

        proc = nuke_process(self._tempfile, self.range)
        self.proc = proc
        self.handle_output(proc)
        self.info(
            '执行任务: {0.path} 优先级:{0.priority} pid: {1}'.format(self, proc.pid))
        self.process_finished.emit(proc.wait())

    def on_process_finished(self, retcode):
        self.info('渲染进程结束: ' + '退出码: {}'.format(retcode)
                  if retcode else '正常退出')

        with database.util.session_scope() as sess:
            self.update_file(sess, is_recreate=False)
            if self.is_aborting:
                self.info('中途终止进程 pid: {}'.format(self.proc.pid))
            elif self.file.hash != self._filehash:
                self.info('文件有更改, 重新加入队列.')
            elif retcode:
                self._handle_render_error()
            else:
                self._handle_normal_ext()

        self._try_remove_tempfile()
        self.state &= ~model.DOING
        self._commit_records()
        if self.is_aborting:
            self.aborted.emit()
        else:
            self.finished.emit()
        return retcode

    def on_frame_finished(self, data):
        assert isinstance(data, dict), type(dict)
        frame, cost, current, total = (data['frame'],
                                       data['cost'],
                                       data['current'],
                                       data['total'])
        if current == 1:
            first_frame = frame
            last_frame = first_frame + total - 1
            self.frames = total

            with database.util.session_scope() as sess:
                self.update_file(sess, is_recreate=False)
                self._update_file_range(first_frame, last_frame)
                self._set_state(model.PARTIAL,
                                self.range != self.file.range())

        self.progressed.emit(current * 100 / total)
        self._info_timestamp()

        frame_record = dict(
            file_hash=self._filehash,
            frame=frame,
            cost=cost,
            timestamp=time.time())
        self._frames_records.append(frame_record)
        if not self._last_commit_time or time.time() - self._last_commit_time > 5:
            self._commit_records()

    def _commit_records(self):
        records, self._frames_records = self._frames_records, []
        with database.util.session_scope() as sess:
            self.update_file(sess, is_recreate=False)
            sess.bulk_insert_mappings(database.Frame, records)
            while self._output_records:
                output_record = sess.merge(
                    database.Output(**self._output_records.pop(0)))
                output_record.files.append(self.file)
        self._last_commit_time = time.time()

    def on_started(self):
        self.state |= model.DOING
        self._info_timestamp()

    def on_progressed(self, value):
        now = time.clock()
        if (self.last_progress_time
                and now - self.last_progress_time < self.min_progress_interval):
            return

        self.last_progress_time = now
        with database.util.session_scope() as sess:
            self._update_estimate(sess)
        self.remains = (1.0 - value / 100.0) * self.estimate

    def on_finished(self):
        if self.is_aborting:
            return
        now = time.time()
        cost = now - self.start_time

        with database.util.session_scope() as sess:
            self.update_file(sess, is_recreate=False)
            self.file.last_finish_time = now
            self.file.last_cost = cost

        self.info('{}: 结束渲染 耗时 {}'.format(
            self.path,
            pendulum.duration(seconds=cost).in_words()))

    def on_output_updated(self, payload):
        path = payload['path']
        frame = payload['frame']

        record = dict(
            path=path,
            timestamp=pendulum.now(),
            frame=frame,
        )
        self._output_records.append(record)

    def _handle_render_error(self):
        self.error_count += 1
        self.priority -= 1
        self.error('{}: 渲染出错 第{}次'.format(
            self.path, self.error_count))
        if self.error_count >= self.max_retry:
            self.error('渲染错误达到{}次,不再进行重试。'.format(self.max_retry))
            self.state |= model.DISABLED

    def _handle_normal_ext(self):
        if self.state & model.PARTIAL or CONFIG['PROXY']:
            self.state |= model.DISABLED
        else:
            self.state |= model.FINISHED
            self.info('任务完成')
            self.file.archive()

    def _try_remove_tempfile(self):
        try:
            os.remove(self._tempfile)
        except OSError:
            self.error('移除临时文件失败: {}'.format(self._tempfile))
            LOGGER.warning('Remove temprory file failed.', exc_info=True)

    def _info_timestamp(self):
        now = time.clock()
        if (self._last_timestamp_time
                and now - self._last_timestamp_time < self.min_timestamp_interval):
            return

        self._last_timestamp_time = now
        self.stdout.emit(texttools.stylize(time.strftime('[%x %X]'), 'info'))


def nuke_process(filepath, range_):
    """Nuke render process for file @f.  """

    filepath = os.path.normpath(u(filepath))

    options = _options_from_config()
    if range_:
        options.extend(('-F', range_))
    args = [CONFIG['NUKE'], '-x'] + options + [filepath]
    args = [u(i) for i in args]  # int, bytes -> str
    LOGGER.debug('Popen: %s', args)
    kwargs = {
        'stdout': PIPE,
        'stderr': PIPE,
        'cwd': CONFIG['DIR']
    }
    if sys.platform == 'win32':
        kwargs['cwd'] = e(kwargs['cwd'])
    proc = Popen(args, **kwargs)
    return proc


def _options_from_config():
    ret = ['-p' if CONFIG['PROXY'] else '-f']
    conditional_options = {
        'CONTINUE': ('--cont',),
        'LOW_PRIORITY': ('--priority', 'low'),
        'THREADS': ('-m', CONFIG['THREADS']),
        'MEMORY_LIMIT': ('-c', '{}M'.format(int(CONFIG['MEMORY_LIMIT'] * 1024)))
    }

    for k, v in conditional_options.items():
        if CONFIG[k]:
            ret.extend(v)
    return ret
