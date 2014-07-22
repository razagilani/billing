from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
import billing.data.model

class Base(object):

    @classmethod
    def column_names(cls):
        return [prop.key for prop in class_mapper(cls).iterate_properties
                if isinstance(prop, ColumnProperty)]

    @classmethod
    def get(cls, _id):
        session = billing.data.model.orm.Session()
        return session.query(cls).filter_by(id=_id).one()

    def __eq__(self, other):
        try:
            return all([getattr(self, x) == getattr(other, x) for x in
                        self.column_names()])
        except AttributeError:
            return False

    def column_dict(self):
        return {c: getattr(self, c) for c in self.column_names()}

from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base(cls=Base)
Session = scoped_session(sessionmaker())
