# -*- mode: python -*-

block_cipher = None


a = Analysis(['launch.py'],
             pathex=[
                 ''],
             binaries=[],
             datas=[('lib/batchrender/bin/', 'batchrender/bin'),
                    ('lib/batchrender/console.css', 'batchrender'),
                    ('lib/batchrender/batchrender.zh_CN.json', 'batchrender'),
                    ('lib/batchrender/view/mainwindow.ui', 'batchrender/view'), ],
             hiddenimports=['PySide.QtUiTools',
                            'PySide.QtCore',
                            'PySide.QtGui',
                            'PySide.QtXml',
                            'sqlalchemy.ext.baked'],
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
