import unittest
from reebill.reebill_model import ReeBillCustomer, CustomerGroup


class CustomerGroupTest(unittest.TestCase):

    def test_group_membership(self):
        g = CustomerGroup(name='a')
        a = ReeBillCustomer()
        b = ReeBillCustomer()

        self.assertEqual([], g.get_customers())
        self.assertEqual([], a.get_groups())

        g.add(a)
        self.assertEqual([a], g.get_customers())
        self.assertEqual([g], a.get_groups())

        g.add(b)
        self.assertEqual({a, b}, set(g.get_customers()))
        self.assertEqual([g], a.get_groups())
        self.assertEqual([g], b.get_groups())

        g.remove(a)
        self.assertEqual([b], g.get_customers())
        self.assertEqual([], a.get_groups())
        self.assertEqual([g], b.get_groups())

        # note: 'b.groups' here appears to be [] because that attribute does
        # not get updated along with g.customers

    def test_2(self):
        g = CustomerGroup(name='a')
        a = ReeBillCustomer()
        print g.customers, a.groups
        g.add(a)
        print g.customers, a.groups
        print g.customers == [a]
        print a.groups == [g]
