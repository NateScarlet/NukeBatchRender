# -*- coding=UTF-8 -*-
"""App gui view.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
from PySide2.QtCore import QCoreApplication


class UnicodeTrMixin(object):
    """Mixin for use `QCoreApplication.translate` with `unicode_literals`.  """
    # pylint: disable=too-few-public-methods

    def tr(self, key, disambiguation=None, encoding=-1):  # pylint: disable=invalid-name
        """Override.  """

        context = self.__class__.__name__
        if isinstance(key, bytes):
            key = key.decode('utf-8')
        return QCoreApplication.translate(context, key, disambiguation, encoding)
