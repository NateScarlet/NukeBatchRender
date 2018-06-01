#! /usr/bin/env python
# -*- coding=UTF-8 -*-
"""Let script only run once at a time.

SingleInstance modified from: https://pypi.python.org/pypi/tendo
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import sys
import tempfile
import unittest

import six

from . import filetools

try:
    if sys.platform != 'win32':
        import fcntl
except ImportError:
    raise

LOGGER = logging.getLogger("singleton")

__version__ = '0.2.0'


class SingleInstance(object):
    """instantiate this class and hold it on a dummy constant to keep singleinstance.  """

    def __init__(self, flavor_id="", on_exit=None):
        self.initialized = False
        self.on_exit = on_exit
        basename = os.path.splitext(os.path.abspath(sys.argv[0]))[0].replace(
            "/", "-").replace(":", "").replace("\\", "-") + '-{}'.format(flavor_id) + '.lock'
        self.lockfile = os.path.normpath(
            tempfile.gettempdir() + '/' + basename)

        LOGGER.debug("Singleton lockfile: " + self.lockfile)

        self.check()
        self.initialized = True

    def __del__(self):
        if not self.initialized:
            return

        if sys.platform == 'win32':
            self.file.close()
        else:
            fcntl.lockf(self.file, fcntl.LOCK_UN)

        if os.path.isfile(self.lockfile):
            os.remove(self.lockfile)

    def check(self):
        """Check if singleton.  """
        existed = False
        if sys.platform == 'win32':
            try:
                # file already exists, we try to remove (in case previous
                # execution was interrupted)
                if os.path.exists(self.lockfile):
                    os.remove(self.lockfile)
                self.file = open(self.lockfile, 'w')
            except OSError as ex:
                if ex.errno == 13:
                    existed = True
        else:  # non Windows
            self.file = open(self.lockfile, 'w')
            try:
                fcntl.lockf(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                existed = True
        if existed:
            LOGGER.info("已经有其他实例在运行了.  ")
            self.exit()
        pid = os.getpid()
        with open(self.lockfile, 'w') as f:
            f.write(str(pid))
            LOGGER.debug('Write pid %s to lockfile', pid)

    def exit(self):
        """Exit scrpit."""
        with open(self.lockfile) as f:
            pid = f.read()
            active_pid(pid)
        sys.exit(-1)


class _SingletonTestCase(unittest.TestCase):
    @classmethod
    def _f(cls, name):
        tmp = LOGGER.level
        LOGGER.setLevel(logging.CRITICAL)  # we do not want to see the warning
        dummy = SingleInstance(flavor_id=name)
        print(name, 'doing something.')
        LOGGER.setLevel(tmp)

    @staticmethod
    def test_1():
        dummy = SingleInstance(flavor_id="test-1")
        del dummy  # now the lock should be removed
        assert True

    def test_2(self):
        proc = Process(target=self._f, args=("test-2",))
        proc.start()
        proc.join()
        # the called function should succeed
        assert proc.exitcode == 0, "%s != 0" % proc.exitcode

    def test_3(self):
        dummy = SingleInstance(flavor_id="test-3")
        proc = Process(target=self._f, args=("test-3",))
        proc.start()
        proc.join()
        # the called function should fail because we already have another
        # instance running
        assert proc.exitcode != 0, "%s != 0 (2nd execution)" % proc.exitcode
        # note, we return -1 but this translates to 255 meanwhile we'll
        # consider that anything different from 0 is good
        proc = Process(target=self._f, args=("test-3",))
        proc.start()
        proc.join()
        # the called function should fail because we already have another
        # instance running
        assert proc.exitcode != 0, "%s != 0 (3rd execution)" % proc.exitcode


def active_pid(pid):
    """Active window by pid.  """

    try:
        int(pid)
    except (ValueError, TypeError):
        return
    pid = six.text_type(pid)
    LOGGER.info('激活已经打开的实例 pid: %s', pid)
    if sys.platform == 'win32':
        filetools.popen(['winactive_by_pid', pid])
    else:
        filetools.popen(
            'xdotool windowactivate $(xdotool search --pid {} -name| tail -n1)'.format(pid),
            shell=True)


if __name__ == "__main__":
    from multiprocessing import Process
    LOGGER.addHandler(logging.StreamHandler())
    LOGGER.setLevel(logging.DEBUG)
    unittest.main()
