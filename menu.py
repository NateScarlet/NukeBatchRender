# -*- coding: UTF-8 -*-
"""Add menu to nuke.  """
import nuke

import batchrender


def _add_menu():

    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')
    m.addCommand('批渲染', batchrender.call_from_nuke)


_add_menu()
