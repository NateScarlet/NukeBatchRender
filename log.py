# -*- coding=UTF-8 -*-
"""Task rendering.  """
from __future__ import print_function, unicode_literals

import multiprocessing
import sys
import threading
import traceback

import logging


class MultiProcessingHandler(logging.Handler):
    """Multiprocessing rotate file log handler.  """

    def __init__(self, handler, args=(), kwargs=()):
        logging.Handler.__init__(self)

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
