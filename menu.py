# -*- coding: UTF-8 -*-
"""Add menu to nuke.  """

import os
import sys

import nuke


def _add_menu():

    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    from batchrender import call_from_nuke as batchrender
    sys.path.remove(current_dir)

    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')
    m.addCommand('批渲染', batchrender)


_add_menu()
del _add_menu
