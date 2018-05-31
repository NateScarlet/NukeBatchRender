# -*- coding=UTF-8 -*-
"""Thread tools.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import threading
from functools import wraps


def run_async(func):
    """Run func in thread.  """

    @wraps(func)
    def _func(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return _func
