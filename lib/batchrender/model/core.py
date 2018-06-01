# -*- coding=UTF-8 -*-
"""Data models for batchrender.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from Qt.QtCore import Qt

ROLE_PRIORITY = Qt.UserRole + 4
ROLE_RANGE = Qt.UserRole + 5
ROLE_STATUS = Qt.UserRole + 6
ROLE_REMAINS = Qt.UserRole + 7
ROLE_ESTIMATE = Qt.UserRole + 8
ROLE_FRAMES = Qt.UserRole + 9
ROLE_FILE = Qt.UserRole + 10
ROLE_ERROR_COUNT = Qt.UserRole + 11

DOING = 1 << 0
DISABLED = 1 << 1
FINISHED = 1 << 2
