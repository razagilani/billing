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

    # TODO: remove this. it demonstrates that every object related to
    # UtilBill is copied along with UtilBill, which we don't want.
    def test_1(self):
        from core.model import UtilBill, Utility, UtilityAccount
        u1 = Utility(name='1')
        u2 = Utility(name='2')
        a = UtilityAccount('a', '111', None, None, None, None, None)
        u = UtilBill(a, u1, None)
        v = UtilBill(a, u2, None)
        v._copy_data_from(u)
        print id(u.utility_account), id(v.utility_account)
