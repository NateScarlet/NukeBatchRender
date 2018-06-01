# -*- coding=UTF-8 -*-
"""Subprocess handler.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import re
import subprocess
import sys
import threading
import time

import six
from Qt.QtCore import QObject, Signal

from ..config import CONFIG
from ..texttools import l10n, stylize
from ..threadtools import run_async

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

    def start(self):
        """Start handler output.  """

        self._handle_stderr()
        self._handle_stdout()
        if sys.platform == 'win32':
            self._handle_werfault()

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

            self.stdout.emit(stylize(l10n(line), 'stdout'))
            self._match_stdout(line, context)

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

    def _handle_werfault(self):
        if self.proc.poll() is not None:
            return

        _close_werfault(self.proc.pid)
        timer = threading.Timer(2.0, self._handle_werfault)
        timer.start()


def _close_werfault(pid):
    args = ['WMIC', 'process', 'where',
            "name='werfault.exe' and commandline like '%-p {}%'".format(pid),
            'get', 'processid', '/format:list']
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = proc.communicate()
    match = re.match(r'\s*ProcessId=(\d+)', stdout)
    if match:
        pid = match.group(1)
        subprocess.call(
            ['TASKKILL', '/pid', pid]
        )
