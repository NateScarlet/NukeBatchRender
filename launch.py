# -*- coding=UTF-8 -*-
"""Launch batch render.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys

import batchrender.__main__

if __name__ == '__main__':
    if sys.platform == 'win32':
        import win_unicode_console
        win_unicode_console.enable()
    batchrender.__main__.main()
