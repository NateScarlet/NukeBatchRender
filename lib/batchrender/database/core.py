"""Database core functionality.   """

import logging

from pathlib2 import PurePath
from sqlalchemy import TypeDecorator, Unicode, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import sessionmaker

from ..codectools import get_unicode as u, get_encoded as e
from ..config import CONFIG

Base = declarative_base()  # pylint: disable=invalid-name
Session = sessionmaker()  # pylint: disable=invalid-name
LOGGER = logging.getLogger(__name__)


class Path(TypeDecorator):
    """Path type."""
    # pylint: disable=abstract-method

    impl = Unicode

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = u(value).replace('\\', '/')
            value = PurePath(value).as_posix()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = PurePath(e(value))
        return value


class SerializableMixin(object):
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
