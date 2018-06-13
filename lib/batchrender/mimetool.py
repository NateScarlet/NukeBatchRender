# -*- coding=UTF-8 -*-
"""Tools for mimetypes.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import mimetypes

import six


def setup():
    mimetypes.add_type('.exr', 'image/exr')


def is_mimetype(filename, type_):
    """Check mimetype through filename.

    Args:
        filename (str): Filename.
        type_ (str, tuple): Types to check.

    Returns:
        bool: Test result.
    """

    filename = six.text_type(filename)
    mime, _ = mimetypes.guess_type(filename)
    return mime and mime.startswith(type_)
