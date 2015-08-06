"""Unit tests for the core.model.Base class, which contains methods shared by
all SQLAlchemy model objects."""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from core.model import Base
from test.testing_utils import TestCase


class B(Base):
    """Example class used in test below.
    """
    __tablename__ = 'b'
    id = Column(Integer, primary_key=True)
    a_id = Column(Integer, ForeignKey('a.id'))

    def __eq__(self, other):
        # two Bs with different primary keys can be equal
        return self.__class__ == other.__class__ and self.a_id == other.a_id


class A(Base):
    """Example class used in test below. Includes all attribute types:
    primary key, regular column, foreign key, and relationship.
    """
    __tablename__ = 'a'
    id = Column(Integer, primary_key=True)
    x = Column(Integer)
    bs = relationship(B, backref='a')


class BaseTest(TestCase):

    def test_copy_data_from(self):
        # a1's attributes are filled in, a2's are empty
        b = B()
        a1 = A(id=1, x=1, bs=[b])
        a2 = A(id=2)

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
        # TODO: this fails because 'b' is getting copied, so the new B object
        # is not the same one as 'b'. i am not sure whether copying is the
        # right behavior or not.
        self.assertEqual(a1, b.a)
        self.assertEqual(3, a1.x)

        # primary keys should not be affected
        self.assertEqual(a1.id, 1)
        self.assertEqual(a2.id, 2)

        # child objects of the object whose _copy_data_from method was called
        # get copied, so the original object still has them, and both objects
        #  have equal ones but not literally the same
        self.assertEqual([b], a2.bs)
        self.assertIsNot(a1.bs[0], a2.bs[0])

        # parent objects do not get copied
        new_b = B(id=4)
        new_b._copy_data_from(b)
        self.assertIs(b.a, new_b.a)
