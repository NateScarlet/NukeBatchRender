# -*- coding=UTF-8 -*-
"""Build exe on windows.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from subprocess import Popen
import os
import webbrowser


from batchrender.__about__ import __version__


def main():
    ouptut = 'dist/batchrender-{}.exe'.format(__version__)

    os.chdir(os.path.dirname(__file__))

    print('Building {}\n'.format(ouptut))

    proc = Popen('pyinstaller -F main.spec')
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
