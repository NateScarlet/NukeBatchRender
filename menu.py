# -*- coding: UTF-8 -*-
import nuke
import nukescripts
from batchrender import EXE_PATH


def _add_menu():
    menubar = nuke.menu("Nuke")
    m = menubar.addMenu('工具')
    m.addCommand(
        '批渲染   ', lambda: nukescripts.start('file://{}'.format(EXE_PATH)))


_add_menu()
