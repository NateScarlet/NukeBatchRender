# -*- coding=UTF-8 -*-
"""Build exe on windows.  """
from subprocess import Popen
import os
import webbrowser


from __version__ import __version__


def main():
    ouptut = 'dist/batchrender-{}.exe'.format(__version__)

    os.chdir(os.path.dirname(__file__))

    print('Building {}\n'.format(ouptut))

    proc = Popen('pyinstaller -F batchrender.spec')
    proc.wait()
    try:
        if os.path.exists(ouptut):
            os.remove(ouptut)
        os.rename('dist/batchrender.exe', ouptut)
    except OSError:
        print('Can not rename to %s' % ouptut)
    webbrowser.open(os.path.abspath(ouptut))


if __name__ == '__main__':
    main()
