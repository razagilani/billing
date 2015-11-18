import unittest
from reebill.reebill_model import ReeBillCustomer, CustomerGroup


class CustomerGroupTest(unittest.TestCase):

    def test_group_membership(self):
        """Adding/removing customers from groups, listing customers in a
        group, listing groups that contain a customer.
        """
        g = CustomerGroup(name='g')
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

        h = CustomerGroup(name='h')
        h.add(b)
        self.assertEqual({g, h}, set(b.get_groups()))

