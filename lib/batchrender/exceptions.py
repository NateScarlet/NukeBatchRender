# -*- coding=UTF-8 -*-
"""Batch render exceptions.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


class RenderException(Exception):
    """Excpection during rendering.  """


class AlreadyRendering(RenderException):
    """Task already rendering.  """
