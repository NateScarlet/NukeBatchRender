# -*- coding=UTF-8 -*-
"""  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import logging.handlers
import os
import sys
import traceback
from multiprocessing.dummy import Queue, Process

import six

from .codectools import get_unicode as u
from .config import CONFIG

LOGGER = logging.getLogger('log')


def _set_logger():
    logger = logging.getLogger()
    logger.propagate = False

    # Loglevel
    try:
        logger.setLevel(os.getenv('LOGLEVEL'))
    except (TypeError, ValueError):
        logger.setLevel(logging.INFO)

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
        logging.handlers.RotatingFileHandler, path, backupCount=5)
    _formatter = logging.Formatter(
        '%(levelname)-6s[%(asctime)s]:%(name)s: %(message)s', '%x %X')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    if os.stat(path).st_size > 10000:
        try:
            _handler.doRollover()
        except OSError:
            LOGGER.debug('Rollover log file failed.')


class MultiProcessingHandler(Process):
    """Multiprocessing rotate file log handler.  """
    _handler = None

    def __init__(self, handler, *args, **kwargs):
        assert issubclass(handler, logging.Handler)

        self._handler = handler(*args, **kwargs)
        # Patch for use non default encoding.
        if issubclass(handler, logging.StreamHandler):
            def _format(record):
                def _encode(i):
                    if isinstance(i, six.text_type):
                        try:
                            return i.encode(sys.stdout.encoding, 'replace')
                        except:  # pylint: disable=bare-except
                            pass
                    return i

                def _decode(i):
                    if isinstance(i, six.binary_type):
                        try:
                            return u(i)
                        except:  # pylint: disable=bare-except
                            pass
                    return i
                record.msg = _decode(record.msg)
                record.args = tuple(_decode(i) for i in record.args)
                ret = handler.format(self._handler, record)
                return _encode(ret)
            self._handler.format = _format
        self.queue = Queue(-1)

        super(MultiProcessingHandler, self).__init__(name=str(self._handler))

        self.daemon = True
        self.start()

    def __getattr__(self, name):
        return getattr(self._handler, name)

    def run(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:  # pylint:disable=bare-except
                traceback.print_exc(file=sys.stderr)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        """(override)logging.handler.emit  """

        try:
            msg = self._format_record(record)
            self.queue.put_nowait(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # pylint:disable=bare-except
            self.handleError(record)

    def close(self):
        """(override)logging.handler.close  """

        self._handler.close()
