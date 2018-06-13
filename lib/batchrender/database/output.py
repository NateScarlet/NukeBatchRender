# -*- coding=UTF-8 -*-
"""Database output table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from sqlalchemy import Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .core import Base, Path, SerializableMixin

LOGGER = logging.getLogger(__name__)


class Output(Base, SerializableMixin):
    """Output table.  """

    __tablename__ = 'Output'
    id = Column(Integer, primary_key=True)  # pylint: disable = invalid-name
    path = Column(Path)
    timestamp = Column(Float)
    cost = Column(Float)
    file_hash = Column(Integer, ForeignKey('File.hash'))
    file = relationship('File')
