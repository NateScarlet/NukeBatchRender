# -*- coding=UTF-8 -*-
"""Database utility.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import time
from contextlib import contextmanager

from . import core

_CONTEXT = {}


def throttle_commit(session, min_interval=1):
    """Throtted session commit.  """

    context_key = 'last_commit_time'

    last_time = _CONTEXT.get(context_key, 0)
    now = time.time()
    if now - last_time > min_interval:
        session.commit()
        _CONTEXT[context_key] = now


@contextmanager
def session_scope(session=None):
    """Session scope context.  """

    sess = session or core.Session()

    try:
        yield sess
        sess.commit()
    except:
        sess.rollback()
        raise
    finally:
        sess.close()
