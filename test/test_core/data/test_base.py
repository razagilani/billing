"""Unit tests for the core.model.Base class, which contains methods shared by
all SQLAlchemy model objects."""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from core.model import Base
from test.testing_utils import TestCase


class B(Base):
    __tablename__ = 'b'
    id = Column(Integer, primary_key=True)


class A(Base):
    __tablename__ = 'a'
    id = Column(Integer, primary_key=True)
    x = Column(Integer)
    b_id = Column(Integer, ForeignKey('b.id'))
    b = relationship(B, backref='a', uselist=False)


class BaseTest(TestCase):

    def test_copy_data_from(self):
        b = B(id=1)
        a1 = A(x=1, b=b)
        a1.b = b
        a2 = A(x=None)

        # TOD: why does a1.b_id not get set?
        print a1.b_id, a1.b
        assert a1.b_id == 1

        a1._copy_data_from(a2)
        self.assertEqual(None, a1.x)
        self.assertEqual(None, a1.b_id)
        self.assertEqual(None, a1.b)
        self.assertEqual(None, b.a)

        b = B(id=3)
        a2.b = b
        a2.x = 4
        a1._copy_data_from(a2)
        self.assertEqual(3, a1.b_id)
        self.assertEqual(b, a1.b)
        self.assertEqual(4, a1.x)
