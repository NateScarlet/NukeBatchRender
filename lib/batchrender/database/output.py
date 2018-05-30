# -*- coding=UTF-8 -*-
"""Database output table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.orm import relationship

from .core import Base, Path, SerializableMixin
import os
from ..import filetools
from ..config import CONFIG

import logging
LOGGER = logging.getLogger(__name__)


class Output(Base, SerializableMixin):
    """Output table.  """

    __tablename__ = 'Output'
    id = Column(String, primary_key=True)
    path = Column(Path)
    timestamp = Column(Float)
    file_hash = Column(Integer, ForeignKey('File.hash'))
    file = relationship('File')
