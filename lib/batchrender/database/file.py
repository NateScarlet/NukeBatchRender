# -*- coding=UTF-8 -*-
"""Database file table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import shutil
import tempfile

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .. import filetools
from ..codectools import get_encoded as e
from ..codectools import get_unicode as u
from ..config import CONFIG
from .core import Base, Path, SerializableMixin

LOGGER = logging.getLogger(__name__)


class File(Base, SerializableMixin):
    """Frame table.  """

    __tablename__ = 'File'
    hash = Column(String, primary_key=True)
    label = Column(String)
    first_frame = Column(Integer)
    last_frame = Column(Integer)
    last_cost = Column(Float)
    last_finish_time = Column(Float)
    path = Column(Path)
    outputs = relationship('Output',
                           back_populates='file')
    frames = relationship('Frame',
                          back_populates='file')

    @property
    def frame_count(self):
        """Frame count in the file.  """

        first, last = self.first_frame, self.last_frame
        if first and last:
            return last - first
        return None

    def estimate_cost(self, frame_count=None, default_frame_count=100, default_frame_cost=30):
        """Estimate file render time cost.  """

        frame_count = frame_count or self.frame_count or default_frame_count
        frames = self.frames
        if not frames:
            return frame_count * default_frame_cost
        costs = (i.cost for i in frames if i.cost)
        frame_cost = sum(costs) / len(costs)
        return frames * frame_cost

    def archive(self, dest='文件备份'):
        """Move file to a folder with hash renamed.  """

        src = self.path
        dest = os.path.join(CONFIG['DIR'], dest, self.filename_with_hash())
        LOGGER.debug('Archiving file: %s -> %s', src, dest)

        shutil.move(e(src), e(dest))

    def create_tempfile(self, dirname='render'):
        """Create a copy in tempdir for render, caller is responsible for deleting.  """

        dirpath = os.path.join(CONFIG['DIR'], dirname)
        try:
            os.makedirs(dirpath)
        except OSError:
            pass
        dst = os.path.join(dirpath, self.filename_with_hash())
        filetools.copy(self.path.as_posix(), dst)
        return dst

    def filename_with_hash(self):
        """Get filename with hash in middle.  """

        path = self.path
        return '{}.{}{}'.format(path.stem, self.hash[:8], path.suffix)

    @classmethod
    def from_path(cls, path, session):
        """Create `File` object from path.  """

        path = u(path)
        hexdigest = filetools.filehash_hex(path)
        label = os.path.basename(e(path))
        ret = session.query(cls).get(hexdigest) or cls(hash=hexdigest)
        assert isinstance(ret, cls), type(ret)
        session.add(ret)
        ret.label = label
        ret.path = path
        session.commit()
        return ret