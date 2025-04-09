# -*- coding=UTF-8 -*-
"""Add menu to nuke.  """

import logging
import subprocess
import sys
import webbrowser
from os import listdir
from os.path import abspath, dirname, getmtime, join

import nuke  # pylint: disable=import-error

LOGGER = logging.getLogger('batchrender')
__folder__ = dirname(abspath(__file__))


def _add_menu():
    sys.path[0] = join(__folder__, 'lib')
    from batchrender.config import CONFIG

    launch_script_path = join(__folder__, 'launch.py')

    def batchrender():
        """For nuke menu call.  """

        CONFIG.read()
        CONFIG['NUKE'] = sys.executable

        if sys.platform == 'win32':
            # Try use built executable
            try:
                dist_dir = join(__folder__, 'dist')
                exe_path = sorted([join(dist_dir, i)
                                   for i in listdir(dist_dir)
                                   if i.endswith('.exe') and i.startswith('batchrender')],
                                  key=getmtime, reverse=True)[0]
                webbrowser.open(exe_path)
                return
            except (IndexError, OSError):
                LOGGER.debug('Executable not found in %s', dist_dir)

        args = [sys.executable, '--tg', launch_script_path]
        if sys.platform == 'win32':
            args = [join(dirname(sys.executable), 'python.exe'),
                    launch_script_path]
            kwargs = {'creationflags': subprocess.CREATE_NEW_CONSOLE}
        else:
            args = '"{0[0]}" {0[1]} "{0[2]}"'.format(args)
            kwargs = {'shell': True, 'executable': 'bash'}
        subprocess.Popen(args, **kwargs)

    globals()['batchrender'] = batchrender

    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')
    m.addCommand('批渲染', batchrender)


_add_menu()
del _add_menu
