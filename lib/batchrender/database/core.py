"""Database core functionality.   """

import logging
from functools import wraps
from pathlib import PurePath

import pendulum
from sqlalchemy import (Column, Float, ForeignKey, String, Table,
                        TypeDecorator, Unicode, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import sessionmaker

from ..codectools import get_unicode as u
from ..config import CONFIG

Base = declarative_base()  # pylint: disable=invalid-name
Session = sessionmaker()  # pylint: disable=invalid-name
LOGGER = logging.getLogger(__name__)


def _skip_process_if_is_none(process):

    @wraps(process)
    def _process(self, value, dialect):
        if value is None:
            return value
        return process(self, value, dialect)

    return _process


class Path(TypeDecorator):
    """Path type."""
    # pylint: disable=abstract-method

    impl = Unicode
    python_type = PurePath

    @_skip_process_if_is_none
    def process_bind_param(self, value, dialect):

        ret = u(value)
        ret = ret.replace('\\', '/')
        PurePath(ret)  # test init.
        return ret

    @_skip_process_if_is_none
    def process_result_value(self, value, dialect):
        return PurePath(value)


class TimeStamp(TypeDecorator):
    """TimeStamp type."""
    # pylint: disable=abstract-method

    impl = Float
    python_type = pendulum.DateTime

    @_skip_process_if_is_none
    def process_bind_param(self, value, dialect):
        if isinstance(value, pendulum.DateTime):
            value = value.timestamp()
        return value

    @_skip_process_if_is_none
    def process_result_value(self, value, dialect):
        return pendulum.from_timestamp(float(value))


FILE_OUTPUT = Table('File-Output', Base.metadata,
                    Column('file_hash', String, ForeignKey('File.hash')),
                    Column('output_path', Path, ForeignKey('Output.path')))


class SerializableMixin:
    """Mixin for serialization.   """

    # pylint: disable=too-few-public-methods

    @classmethod
    def _encode(cls, obj):
        if isinstance(obj, PurePath):
            return obj.as_posix()
        return obj

    def serialize(self):
        """Serialize sqlalchemy object to dictionary.  """

        return {i.name: self._encode(getattr(self, i.name)) for i in self.__table__.columns}


def setup(engine_uri=None):
    engine_uri = engine_uri or CONFIG.engine_uri
    LOGGER.debug('Bind to engine: %s', engine_uri)
    engine = create_engine(engine_uri)
    Session.configure(bind=engine)
    Base.metadata.create_all(engine)
