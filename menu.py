# -*- coding: UTF-8 -*-
"""Add menu to nuke.  """
import os
import sys
from subprocess import Popen

import nuke

from batchrender import Config


def _add_menu():
    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')

    cmd = '"{}"'.format(os.path.abspath(
        os.path.join(__file__, '../batchrender.py')))
    if sys.platform == 'win32':
        executable = os.path.abspath(
            os.path.join(sys.executable, '../python.exe'))
        cmd = 'START "batchrender.console" "{}" {}'.format(executable, cmd)

    Config()['NUKE'] = sys.executable
    m.addCommand('批渲染', lambda: Popen(cmd, shell=True))


_add_menu()
