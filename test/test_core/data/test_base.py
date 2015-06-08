"""Unit tests for the core.model.Base class, which contains methods shared by
all SQLAlchemy model objects."""
from sqlalchemy import Column, Integer, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, backref
from core.model import Base

from test.testing_utils import TestCase

class B(Base):
    """Example class used in test below.
    """
    __tablename__ = 'b'
    id = Column(Integer, primary_key=True)
    a_id = Column(Integer, ForeignKey('a.id'))


class A(Base):
    """Example class used in test below.
    """
    __tablename__ = 'a'
    id = Column(Integer, primary_key=True)
    x = Column(Integer)
    bs = relationship(B, backref='a')


class BaseTest(TestCase):

    def test_copy_data_from(self):
        # a1's attributes are filled in, a2's are empty
        b = B()
        a1 = A(x=1, bs=[b])
        a2 = A()

        # copy empty values from a2 to a1
        a1._copy_data_from(a2)
        self.assertEqual(None, a1.x)
        self.assertEqual([], a1.bs)
        self.assertEqual(None, b.a)

        # copy non-empty values from a2 to a1
        b = B(id=2)
        a2.bs = [b]
        a2.x = 3
        a1._copy_data_from(a2)
        self.assertEqual([b], a1.bs)
        self.assertEqual(a1, b.a)
        self.assertEqual(3, a1.x)
