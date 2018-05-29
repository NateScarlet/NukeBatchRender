# -*- coding=UTF-8 -*-
# """Launch batch render.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
import os

if __name__ == '__main__':
    print(sys.path)
    sys.path.append(os.path.join(__file__, 'lib'))
    from batchrender import __main__
    __main__.main()
