# -*- coding=UTF-8 -*-
"""Database output table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from sqlalchemy import Column, Float
from sqlalchemy.orm import relationship

from . import core

LOGGER = logging.getLogger(__name__)


class Output(core.Base, core.SerializableMixin):
    """Output table.  """

    __tablename__ = 'Output'
    path = Column(core.Path, primary_key=True)
    timestamp = Column(Float)
    files = relationship('File', secondary=core.FILE_OUTPUT)
