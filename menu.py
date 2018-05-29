# -*- coding: UTF-8 -*-
"""Add menu to nuke.  """

import os
from os.path import join, abspath, dirname
import sys
import webbrowser
import subprocess
import logging

import nuke

LOGGER = logging.getLogger('batchrender')
__folder__ = dirname(abspath(__file__))


def _add_menu():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    from batchrender.config import CONFIG

    filename = join(__folder__, 'main.py')

    def batchrender():
        """For nuke menu call.  """

        CONFIG.read()
        CONFIG['NUKE'] = sys.executable

        if sys.platform == 'win32':
            # Try use built executable
            try:
                dist_dir = os.path.join(os.path.dirname(filename), 'dist')
                exe_path = sorted([os.path.join(dist_dir, i)
                                   for i in os.listdir(dist_dir)
                                   if i.endswith('.exe') and i.startswith('batchrender')],
                                  key=os.path.getmtime, reverse=True)[0]
                webbrowser.open(exe_path)
                return
            except (IndexError, OSError):
                LOGGER.debug('Executable not found in %s', dist_dir)

        _file = filename.rstrip('c')
        args = [sys.executable, '--tg', _file]
        if sys.platform == 'win32':
            args = [os.path.join(os.path.dirname(
                sys.executable), 'python.exe'), _file]
            kwargs = {'creationflags': subprocess.CREATE_NEW_CONSOLE}
        else:
            args = '"{0[0]}" {0[1]} "{0[2]}"'.format(args)
            kwargs = {'shell': True, 'executable': 'bash'}
        subprocess.Popen(args, **kwargs)
    sys.path.remove(current_dir)
    globals()['batchrender'] = batchrender

    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')
    m.addCommand('批渲染', batchrender)


_add_menu()
del _add_menu
