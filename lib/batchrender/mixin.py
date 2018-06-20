# -*- coding=UTF-8 -*-
"""App gui view.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from Qt.QtCore import QCoreApplication

import six


class UnicodeTrMixin(object):
    """Mixin for use `QCoreApplication.translate` with `unicode_literals`.  """
    # pylint: disable=too-few-public-methods

    def tr(self, key, disambiguation=None, encoding=QCoreApplication.UnicodeUTF8):  # pylint: disable=invalid-name
        """Override.  """

        context = self.__class__.__name__
        if isinstance(key, six.text_type):
            key = key.encode('utf-8')
        return QCoreApplication.translate(context, key, disambiguation, encoding)
