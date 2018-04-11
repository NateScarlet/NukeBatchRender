# -*- mode: python -*-

block_cipher = None


a = Analysis(['main.py'],
             pathex=[
                 ''],
             binaries=[],
             datas=[('console.css', '.'),
                    ('error_handler.exe', '.'),
                    ('active_pid.exe', '.'),
                    ('mainwindow.ui', '.'),
                    ('batchrender.zh_CN.json', '.')],
             hiddenimports=['PySide.QtUiTools',
                            'PySide.QtCore',
                            'PySide.QtGui',
                            'PySide.QtXml'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt5'],
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
          name='batchrender',
          debug=False,
          strip=False,
          upx=True,
          console=True)
