# -*- coding=UTF-8 -*-
"""Subprocess handler.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import re
import time

import six
from Qt.QtCore import QObject, Signal

from ..config import CONFIG
from ..threadtools import run_async
from ..texttools import l10n, stylize

LOGGER = logging.getLogger(__name__)


class BaseHandler(QObject):
    """Base class for process output handler.  """
    stdout = Signal(six.text_type)
    stderr = Signal(six.text_type)
    frame_finished = Signal(dict)


class NukeHandler(BaseHandler):
    """Process output handler for nuke.  """

    def __init__(self, proc):
        super(NukeHandler, self).__init__()
        self.proc = proc
        self.frame_finished.connect(lambda: print('aaa'))

    def start(self):
        """Start handler output.  """

        self._handle_stderr()
        self._handle_stdout()

    @run_async
    def _handle_stderr(self):
        LOGGER.debug('Start handle stderr.')
        while True:
            line = self.proc.stderr.readline()
            if not line:
                break

            line = l10n(line)
            msg = 'STDERR: {}\n'.format(line)
            with open(CONFIG.log_path, 'a') as f:
                f.write(msg)

            self.stderr.emit(stylize(line, 'stderr'))

        LOGGER.debug('Finished thread: handle_stderr')

    @run_async
    def _handle_stdout(self, **context):
        LOGGER.debug('Start handle stdout.')
        start_time = time.clock()
        context['last_frame_time'] = start_time

        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            self._match_stdout(line, context)

            line = l10n(line)
            self.stdout.emit(stylize(line, 'stdout'))

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
