# -*- coding=UTF-8 -*-
"""Logging.  """
from __future__ import print_function, unicode_literals

import os

import multiprocessing
import sys
import threading
import traceback

import logging
import logging.handlers
from config import CONFIG

LOGGER = logging.getLogger('log')


def _set_logger():
    logger = logging.getLogger()
    logger.propagate = False

    # Loglevel
    loglevel = os.getenv('LOGLEVEL', logging.INFO)
    try:
        logger.setLevel(int(loglevel))
    except TypeError:
        logger.warning(
            'Can not recognize env:LOGLEVEL %s, expect a int', loglevel)

    # Stream handler
    _handler = MultiProcessingHandler(logging.StreamHandler)
    if logger.getEffectiveLevel() == logging.DEBUG:
        _formatter = logging.Formatter(
            '%(levelname)-6s[%(asctime)s]:%(filename)s:'
            '%(lineno)d:%(funcName)s: %(message)s', '%H:%M:%S')
    else:
        _formatter = logging.Formatter(
            '%(levelname)-6s[%(asctime)s]:'
            '%(name)s: %(message)s', '%H:%M:%S')

    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.debug('Added stream handler.  ')

    # File handler
    path = CONFIG.log_path
    path_dir = os.path.dirname(path)
    try:
        os.makedirs(path_dir)
    except OSError:
        pass
    _handler = MultiProcessingHandler(
        logging.handlers.RotatingFileHandler,
        args=(path,), kwargs={'backupCount': 5})
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]:%(name)s: %(message)s', '%x %X')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    if os.stat(path).st_size > 10000:
        try:
            _handler.doRollover()
        except OSError:
            LOGGER.debug('Rollover log file failed.')


class MultiProcessingHandler(logging.Handler):
    """Multiprocessing rotate file log handler.  """
    _handler = None

    def __init__(self, handler, args=(), kwargs=None):
        logging.Handler.__init__(self)
        kwargs = kwargs or {}
        self._handler = handler(*args, **kwargs)
        self.queue = multiprocessing.Queue(-1)

        thread = threading.Thread(target=self.receive)
        thread.daemon = True
        thread.start()

    def __getattr__(self, name):
        return getattr(self._handler, name)

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        self._handler.setFormatter(fmt)

    def receive(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:
                traceback.print_exc(file=sys.stderr)

    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        self._handler.close()
        logging.Handler.close(self)
