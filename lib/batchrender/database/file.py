# -*- coding=UTF-8 -*-
"""Database file table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import os
import shutil

import six
from sqlalchemy import Column, Float, Integer, String, func
from sqlalchemy.orm import relationship

from . import core
from .. import filetools
from ..codectools import get_encoded as e
from ..codectools import get_unicode as u
from ..config import CONFIG
from ..framerange import FrameRange
from .core import Base, Path, SerializableMixin
from .frame import Frame
from .output import Output

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
    outputs = relationship('Output', secondary=core.FILE_OUTPUT)
    frames = relationship('Frame',
                          back_populates='file')

    def __new__(cls, *args, **kwargs):
        return super(File, cls).__new__(cls, *args, **kwargs)

    @property
    def frame_count(self):
        """Frame count in the file.  """

        first, last = self.first_frame, self.last_frame
        if first and last:
            return last - first + 1
        return None

    def range(self):
        """File range represition text, returns `None` if not avaliable. """

        first, last = self.first_frame, self.last_frame
        if first is None or last is None:
            return None
        return FrameRange(range(first, last+1))

    def average_frame_cost(self, session):
        """Average frame cost for this file.  """

        return session.query(func.avg(Frame.cost)).filter(Frame.file == self).scalar()

    def estimate_cost(self, session, frame_count=None, default_frame_count=100, default_frame_cost=30):
        """Estimate file render time cost.  """

        frame_cost = (self.average_frame_cost(session) or
                      session.query(func.avg(Frame.cost)).scalar() or
                      default_frame_cost)

        frame_count = frame_count or self.frame_count or default_frame_count

        return frame_cost * frame_count

    def archive(self, dest='文件备份'):
        """Move file to a folder with hash renamed.  """

        src = u(self.path)
        dest = os.path.join(CONFIG['DIR'], dest, self.filename_with_hash())
        LOGGER.debug('Archiving file: %s -> %s', src, dest)

        filetools.ensure_parent_directory(dest)
        shutil.move(e(src), e(dest))

    def create_tempfile(self, dirname='render'):
        """Create a copy in tempdir for render, caller is responsible for deleting.  """

        dst = self._tempfile_path(dirname)
        try:
            os.makedirs(e(os.path.dirname(dst)))
        except OSError:
            pass
        assert isinstance(dst, six.text_type), type(dst)
        filetools.copy(self.path.as_posix(), dst)
        return dst

    def _tempfile_path(self, dirname):
        return os.path.join(_dir_path(dirname), self.filename_with_hash())

    def is_rendering(self, dirname='render'):
        return os.path.exists(e(self._tempfile_path(dirname)))

    def remove_tempfile(self, dirname='render'):
        os.unlink(e(self._tempfile_path(dirname)))

    def filename_with_hash(self):
        """Get filename with hash in middle.  """

        path = self.path
        return '{}.{}{}'.format(u(path.stem), self.hash[:8], u(path.suffix))

    def has_sequence(self, session):
        """If this file has sequence output.  """

        count = session.query(Output.frame).filter(
            Output.files.contains(self)).distinct().count()
        return count > 1

    def rendered_frames(self, session):
        """Current rendered frames.

        Returns:
            FrameRange
        """

        frames = [i for i, in session.query(Output.frame).filter(
            Output.files.contains(self)).distinct().order_by(Output.frame).all()]
        return FrameRange(frames)

    @classmethod
    def from_path(cls, path, session):
        """Create `File` object from path.  """

        path = u(path)
        hexdigest = filetools.filehash_hex(path)
        label = os.path.basename(path)
        ret = session.query(cls).get(hexdigest) or cls(hash=hexdigest)
        assert isinstance(ret, cls), type(ret)
        ret.label = label
        ret.path = path
        session.add(ret)
        session.commit()
        session.refresh(ret)
        return ret


def _dir_path(dirname):
    dirname = u(dirname)
    return os.path.normpath(os.path.join(CONFIG['DIR'], dirname))
