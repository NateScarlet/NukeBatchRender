# -*- mode: python -*-
# pylint: skip-file
import sys

from batchrender.__about__ import __version__

block_cipher = None

sys.modules['FixTk'] = None

a = Analysis(['launch.py'],
             pathex=[''],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=['hooks'],
             runtime_hooks=['runtime_hook.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='batchrender-{}'.format(__version__),
          debug=False,
          strip=False,
          upx=True,
          console=True)
