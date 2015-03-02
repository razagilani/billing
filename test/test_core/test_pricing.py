"""Tests for pricing.py"""
from datetime import date
import unittest

from mock import Mock

from core.pricing import FuzzyPricingModel
from core.model import Charge, UtilBill, RateClass, Utility, Address
from exc import NoSuchBillException

def raise_nsbe(*args, **kwargs):
    raise NoSuchBillException

class FuzzyPricingModelTest(unittest.TestCase):
    """Unit tests for FuzzyPricingModel.
    """
    def setUp(self):
        # 3 rate structures, two containing B shared and one containing B
        # unshared. If unshared RSIs count as "absent", B is more absent than
        # present and should be excluded from a new predicted rate structure.
        # If unshared RSIs count as neutral, B shared occurs 1 out of 1 times,
        # so it should be included in a new predicted rate structure. C is
        # never shared so it never gets included in any bill, except one
        # whose "predecessor" contains it.
        self.charge_a_shared = Charge(utilbill=None,
                                      rsi_binding='A',
                                      rate=1,
                                      quantity_formula='',
                                      description="",
                                      unit='therms',
                                      shared=True,
                                      has_charge=True)
        self.charge_b_unshared = Charge(utilbill=None,
                                        rsi_binding='B',
                                        rate=2,
                                        quantity_formula='',
                                        description="",
                                        unit='therms',
                                        shared=False,
                                        has_charge=True)
        self.charge_b_shared = Charge(utilbill=None,
                                      rsi_binding='B',
                                      rate=2,
                                      quantity_formula='',
                                      description="",
                                      unit='therms',
                                      shared=True,
                                      has_charge=True)
        self.charge_c_unshared = Charge(utilbill=None,
                                        rsi_binding='C',
                                        rate=3,
                                        quantity_formula='',
                                        description="",
                                        unit='therms',
                                        shared=False,
                                        has_charge=False)

        self.utility = Utility(name='Utility', address=Address())
        self.rate_class = RateClass(name='Rate Class', utility=self.utility,
                                    service='gas')

        def make_mock_utilbill(account):
            u = Mock()
            u.customer.account = account
            u.period_start = date(2000,1,1)
            u.period_end = date(2000,2,1)
            u.processed = False
            u.utility = self.utility
            u.rate_class = self.rate_class
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
        self.utilbill_loader = Mock()
        self.fpm = FuzzyPricingModel(self.utilbill_loader)

    def test_get_predicted_charges(self):
        # utility bill for which to predict a rate structure, using the
        # ones created in setUp
        u = Mock(autospec=UtilBill)
        u.utility_account.account = '00004'
        u.period_start = date(2000, 1, 1)
        u.period_end = date(2000, 2, 1)
        u.processed = False
        u.utility = self.utility
        u.rate_class = self.rate_class
        u.charges = []

        # with no processed utility bills, predicted rate structure is empty.
        # note that since 'utilbill_loader' is used, actually loading the
        # utility bills with the given attributes is outside the scope of
        # FuzzyPricingModel
        self.utilbill_loader.get_last_real_utilbill.side_effect = raise_nsbe
        self.utilbill_loader.load_real_utilbills.return_value = []
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.get_last_real_utilbill.assert_called_once_with(
                u.utility_account.account, end=u.period_start,
                utility=u.utility, rate_class=u.rate_class, processed=True)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        self.assertEqual([], charges)

        # with only the 1st utility bill (containing rsi_a_shared and
        # rsi_b_unshared), only rsi_a_shared should appear in the result
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1]
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        self.assertEqual([self.charge_a_shared], charges)

        # with 2 existing utility bills processed, predicted rate structure
        # includes both A (shared) and B (shared)
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # with 3 processed utility bills
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        # see explanation in setUp for why rsi_a_shared and rsi_b_shared
        # should be included here
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # the same is true when the period of 'u' starts after the period of
        # the existing bills
        self.utilbill_loader.reset_mock()
        u.period_start, u.period_end = date(2000,2,1), date(2000,3,1)
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # however, when u belongs to the same account as an existing bill,
        # and that bill meets the requirements to be its "predecessor",
        # un-shared RSIs from the "predecessor" of u also get included.
        self.utilbill_loader.reset_mock()
        u.customer.account = '10001'
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1, self.utilbill_2, self.utilbill_3]
        self.utilbill_loader.get_last_real_utilbill.side_effect = None
        self.utilbill_loader.get_last_real_utilbill.return_value = \
            self.utilbill_1
        charges = self.fpm.get_predicted_charges(u)
        self.utilbill_loader.load_real_utilbills.assert_called_once_with(
                utility=self.utility, rate_class=self.rate_class,
                processed=True)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared,
                self.charge_c_unshared], charges)

    def test_missing_dates(self):
        """Test predicting charges for bills that have a missing start or
        end date or both.
        """
        u = Mock(autospec=UtilBill)
        u.utility_account.account = '00004'
        u.processed = False
        u.utility = self.utility
        u.rate_class = self.rate_class
        u.charges = []

        self.utilbill_loader.get_last_real_utilbill.side_effect = raise_nsbe
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1]

        # if no dates are known, no shared charges are generated
        u.period_start, u.period_end = None, None
        charges = self.fpm.get_predicted_charges(u)
        self.assertEqual([], charges)

        # if only one date is known, that's enough to guess the charges using an
        # estimate of the other date
        u.period_start, u.period_end = None, date(2000,2,1)
        self.assertEqual([self.charge_a_shared],
                         self.fpm.get_predicted_charges(u))
        u.period_start, u.period_end = date(2000,1,1), None
        self.assertEqual([self.charge_a_shared],
                         self.fpm.get_predicted_charges(u))


    # TODO test that the bill whose charges are being generated is ignored when
    # collecting the set of bills to generate charges
