# -*- coding=UTF-8 -*-
"""Build exe on windows.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import webbrowser
from subprocess import Popen

from batchrender.__about__ import __version__

__dirname__ = os.path.abspath(os.path.dirname(__file__))


def main():
    ouptut = '{}/dist/batchrender-{}.exe'.format(__dirname__, __version__)

    print('Building {}\n'.format(ouptut))

    proc = Popen('pyinstaller -F main.spec')
    proc.wait()
    try:
        if os.path.exists(ouptut):
            os.remove(ouptut)
        os.rename('{}/dist/batchrender.exe'.format(__dirname__), ouptut)
    except OSError:
        print('Can not rename to %s' % ouptut)
        sys.exit(1)
    webbrowser.open(ouptut)


if __name__ == '__main__':
    main()
