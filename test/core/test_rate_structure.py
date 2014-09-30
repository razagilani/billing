'''Tests for rate_structure.py'''
from datetime import date
import unittest

from mock import Mock

from billing.processing.rate_structure import RateStructureDAO
from billing.model import Charge
from billing.exc import NoSuchBillException


class RateStructureDAOTest(unittest.TestCase):
    def setUp(self):
        # 3 rate structures, two containing B shared and one containing B
        # unshared. If unshared RSIs count as "absent", B is more absent than
        # present and should be excluded from a new predicted rate structure.
        # If unshared RSIs count as neutral, B shared occurs 1 out of 1 times,
        # so it should be included in a new predicted rate structure. C is
        # never shared so it never gets included in any bill, except one
        # whose "predecessor" contains it.
        self.charge_a_shared = Charge(utilbill=None,
                                      description="",
                                      group='a',
                                      quantity=1,
                                      quantity_units='therms',
                                      rate=1,
                                      rsi_binding='A',
                                      total=1,
                                      shared=True,
                                      has_charge=True)
        self.charge_b_unshared = Charge(utilbill=None,
                                        description="",
                                        group='c',
                                        quantity=2,
                                        quantity_units='therms',
                                        rate=2,
                                        rsi_binding='B',
                                        total=4,
                                        shared=False,
                                        has_charge=True)
        self.charge_b_shared = Charge(utilbill=None,
                                      description="",
                                      group='b',
                                      quantity=2,
                                      quantity_units='therms',
                                      rate=2,
                                      rsi_binding='B',
                                      total=4,
                                      shared=True,
                                      has_charge=True)
        self.charge_c_unshared = Charge(utilbill=None,
                                        description="",
                                        group='d',
                                        quantity=3,
                                        quantity_units='therms',
                                        rate=3,
                                        rsi_binding='C',
                                        total=9,
                                        shared=False,
                                        has_charge=False)

        def make_mock_utilbill(account):
            u = Mock()
            u.customer.account = account
            u.period_start = date(2000,1,1)
            u.period_end = date(2000,2,1)
            u.processed = False
            u.service = 'gas'
            u.utility = 'washgas'
            u.rate_class = 'whatever'
            return u

        self.utilbill_1 = make_mock_utilbill('00001')
        self.utilbill_2 = make_mock_utilbill('00002')
        self.utilbill_3 = make_mock_utilbill('00003')

        self.utilbill_1.charges = [self.charge_a_shared,
                                   self.charge_b_unshared,
                                   self.charge_c_unshared]

        self.utilbill_2.charges = [self.charge_a_shared,
                                   self.charge_b_unshared]

        self.utilbill_3.charges = [self.charge_b_shared]
        self.dao = RateStructureDAO()

    def test_get_predicted_charges(self):
        utilbill_loader = Mock()

        # utility bill for which to predict a rate structure, using the
        # ones created in setUp
        u = Mock()
        u.customer.account = '00004'
        u.period_start = date(2000, 1, 1)
        u.period_end = date(2000, 2, 1)
        u.processed = False
        u.service = 'gas'
        u.utility = 'washgas'
        u.rate_class = 'whatever'
        u.charges = []

        # with no processed utility bills, predicted rate structure is empty.
        # note that since 'utilbill_loader' is used, actually loading the
        # utility bills with the given attributes is outside the scope of
        # RateStructureDAO
        def raise_nsbe(*args, **kwargs):
            raise NoSuchBillException
        utilbill_loader.get_last_real_utilbill.side_effect = raise_nsbe
        utilbill_loader.load_real_utilbills.return_value = []
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.get_last_real_utilbill.assert_called_once_with(
                u.customer.account, u.period_start,
                service=u.service, utility=u.utility,
                rate_class=u.rate_class, processed=True)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([], rs)

        # with only the 1st utility bill (containing rsi_a_shared and
        # rsi_b_unshared), only rsi_a_shared should appear in the result
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1]
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.charge_a_shared], rs)

        # with 2 existing utility bills processed, predicted rate structure
        # includes both A (shared) and B (shared)
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], rs)

        # with 3 processed utility bills
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        # see explanation in setUp for why rsi_a_shared and rsi_b_shared
        # should be included here
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], rs)

        # the same is true when the period of 'u' starts after the period of
        # the existing bills
        utilbill_loader.reset_mock()
        u.period_start, u.period_end = date(2000,2,1), date(2000,3,1)
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], rs)

        # however, when u belongs to the same account as an existing bill,
        # and that bill meets the requirements to be its "predecessor",
        # un-shared RSIs from the "predecessor" of u also get included.
        utilbill_loader.reset_mock()
        u.customer.account = '10001'
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                                            self.utilbill_2, self.utilbill_3]
        utilbill_loader.get_last_real_utilbill.side_effect = None
        utilbill_loader.get_last_real_utilbill.return_value = self.utilbill_1
        rs = self.dao.get_predicted_charges(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared,
                self.charge_c_unshared], rs)


    # TODO test that RS of the bill being predicted is ignored, whether or not
    # that RS exists in the db yet

if __name__ == '__main__':
    unittest.main(failfast=True)
