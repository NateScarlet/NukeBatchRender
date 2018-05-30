# -*- coding=UTF-8 -*-
"""Database frame table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


from sqlalchemy import Column, ForeignKey, Integer, Float, func
from sqlalchemy.orm import relationship
from .core import Base, SerializableMixin


class Frame(Base, SerializableMixin):
    """Frame table.  """

    __tablename__ = 'Frame'
    id = Column(Integer, primary_key=True)
    frame = Column(Integer)
    cost = Column(Float)
    timestamp = Column(Float)
    file_hash = Column(Integer, ForeignKey('File.hash'))
    file = relationship('File')

    @classmethod
    def average_cost(cls, session):
        return session.query(func.average(cls.cost)).one()
