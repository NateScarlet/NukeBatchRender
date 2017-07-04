# -*- coding: UTF-8 -*-
import nuke

_menubar = nuke.menu("Nuke")
m = _menubar.addMenu('批渲染')
m.addCommand('批渲染', "import batchrender;nukescripts.start('file://' + batchrender.EXE_PATH)")
