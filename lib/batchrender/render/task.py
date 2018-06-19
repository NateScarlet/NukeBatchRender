# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import sys
import time
from subprocess import PIPE, Popen

from Qt.QtCore import Signal, Slot

from . import core
from .. import database, model, texttools
from ..codectools import get_encoded as e
from ..codectools import get_unicode as u
from ..config import CONFIG
from ..threadtools import run_async
from .proc_handler import NukeHandler

LOGGER = logging.getLogger(__name__)


class NukeTask(model.Task, core.RenderObject):
    """Nuke render task.  """

    frame_finished = Signal(dict)
    process_finished = Signal(int)

    max_retry = 3

    def __init__(self, index, dir_model):
        super(NukeTask, self).__init__(index, dir_model)

        self._tempfile = None
        self._filehash = None
        self.proc = None
        self.start_time = None

        self.frame_finished.connect(self.on_frame_finished)
        self.process_finished.connect(self.on_process_finished)

    def __eq__(self, other):
        if isinstance(other, model.Task):
            other = other.path
        return self.path == other

    def stop(self):
        """Stop rendering.  """

        self.is_stopping = True
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

    def run(self):
        """(Override)"""

        self.start_time = time.time()
        self.is_stopping = False
        self.state |= model.DOING

        self._update_file()
        self._tempfile = self.file.create_tempfile()
        self._filehash = self.file.hash
        self.run_process()

        self.started.emit()

    @run_async
    def run_process(self):
        """Run render process.  """

        proc = nuke_process(self._tempfile, self.range)
        self.proc = proc
        self.handle_output(proc)
        self.info(
            '执行任务: {0.path} 优先级:{0.priority} pid: {1}'.format(self, proc.pid))
        self.process_finished.emit(proc.wait())

    def on_process_finished(self, retcode):
        self.info('渲染进程结束: ' + '退出码: {}'.format(retcode)
                  if retcode else '正常退出')

        self._update_file()
        if self.is_stopping:
            self.info('中途终止进程 pid: {}'.format(self.proc.pid))
        elif self.file.hash != self._filehash:
            self.info('文件有更改, 重新加入队列.')
        elif retcode:
            self._handle_render_error()
        else:
            self._handle_normal_ext()

        self._try_remove_tempfile()
        self.state &= ~model.DOING
        if self.is_stopping:
            self.stopped.emit()
        else:
            self.finished.emit()
        return retcode

    @Slot(dict)
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
            self._update_file_range(first_frame, last_frame)
            self._set_state(model.PARTIAL,
                            self.range != self.file.range())

        frame_record = database.Frame(
            file=self.file, frame=frame, cost=cost, timestamp=time.time())
        database.SESSION.add(frame_record)
        database.util.throttle_commit(database.SESSION)

        self.progressed.emit(current * 100 / total)

    def on_progressed(self, value):
        self._info_timestamp()
        self._update_estimate()
        self.remains = (1.0 - value / 100.0) * self.estimate

    def on_started(self):
        self._info_timestamp()

    def on_finished(self):
        if self.is_stopping:
            return
        now = time.time()
        cost = now - self.start_time
        self.file.last_finish_time = now
        self.file.last_cost = cost
        self.info('{}: 结束渲染 耗时 {}'.format(self.path, cost))
        database.SESSION.commit()

    def on_output_updated(self, payload):
        path = payload['path']
        frame = payload['frame']

        record = (database.SESSION.query(database.Output).get(path)
                  or database.Output(path=path))
        assert isinstance(record, database.Output)
        record.timestamp = time.time()
        record.files += [self.file]
        record.frame = frame
        database.SESSION.add(record)
        database.SESSION.commit()

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
