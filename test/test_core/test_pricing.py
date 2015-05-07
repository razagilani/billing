"""Tests for pricing.py"""
from datetime import date
import unittest

from mock import Mock, call

from core.pricing import FuzzyPricingModel, PricingModel
from core.model import Charge, UtilBill, RateClass, Utility, Address, Supplier
from exc import NoSuchBillException

class PricingModelTest(unittest.TestCase):
    def test_get_predicted_charges(self):
        """Trivial test for abstract class."""
        pm = PricingModel()
        self.assertRaises(NotImplementedError, pm.get_predicted_charges, Mock())

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
        self.charge_a_shared = Charge(rsi_binding='A',
                                      type='distribution',
                                      rate=1,
                                      formula='',
                                      description="",
                                      unit='therms',
                                      shared=True,
                                      has_charge=True)
        self.charge_b_unshared = Charge(rsi_binding='B',
                                        type='distribution',
                                        rate=2,
                                        formula='',
                                        description="",
                                        unit='therms',
                                        shared=False,
                                        has_charge=True)
        self.charge_b_shared = Charge(rsi_binding='B',
                                      type='distribution',
                                      rate=2,
                                      formula='',
                                      description="",
                                      unit='therms',
                                      shared=True,
                                      has_charge=True)
        self.charge_c_unshared = Charge(rsi_binding='C',
                                        type='distribution',
                                        rate=3,
                                        formula='',
                                        description="",
                                        unit='therms',
                                        shared=False,
                                        has_charge=False)

        self.utility = Utility(name='Utility')
        self.supplier = Supplier(name='Utility')
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

        # target bill for which to generate charges
        self.u = Mock(autospec=UtilBill)
        self.u.utility_account.account = '00004'
        self.u.period_start = date(2000, 1, 1)
        self.u.period_end = date(2000, 2, 1)
        self.u.processed = False
        self.u.utility = self.utility
        self.u.supplier = self.supplier
        self.u.rate_class = self.rate_class
        self.u.charges = []

    def test_get_predicted_charges(self):
        # with no processed utility bills, predicted rate structure is empty.
        # note that since 'utilbill_loader' is used, actually loading the
        # utility bills with the given attributes is outside the scope of
        # FuzzyPricingModel
        self.utilbill_loader.get_last_real_utilbill.side_effect = \
            NoSuchBillException
        self.utilbill_loader.load_real_utilbills.return_value = []
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.get_last_real_utilbill.assert_called_once_with(
            self.u.utility_account.account, end=self.u.period_start,
            utility=self.u.utility, rate_class=self.u.rate_class,
            processed=True)
        load_calls = [
            call(utility=self.utility, rate_class=self.rate_class,
                 processed=True), call(supplier=self.supplier, processed=True)]
        self.utilbill_loader.load_real_utilbills.assert_has_calls(load_calls)
        self.assertEqual([], charges)

        # with only the 1st utility bill (containing rsi_a_shared and
        # rsi_b_unshared), only rsi_a_shared should appear in the result
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1]
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.load_real_utilbills.assert_has_calls(load_calls)
        self.assertEqual([self.charge_a_shared], charges)

        # with 2 existing utility bills processed, predicted rate structure
        # includes both A (shared) and B (shared)
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1, self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.load_real_utilbills.assert_has_calls(load_calls)
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # with 3 processed utility bills
        self.utilbill_loader.reset_mock()
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1, self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.load_real_utilbills.assert_has_calls(load_calls)
        # see explanation in setUp for why rsi_a_shared and rsi_b_shared
        # should be included here
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # the same is true when the period of 'u' starts after the period of
        # the existing bills
        self.utilbill_loader.reset_mock()
        self.u.period_start, self.u.period_end = date(2000,2,1), date(2000,3,1)
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1, self.utilbill_2, self.utilbill_3]
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.load_real_utilbills.assert_has_calls([
            call(utility=self.utility, rate_class=self.rate_class,
                 processed=True),
            call(supplier=self.u.supplier, processed=True)])
        self.assertEqual([self.charge_a_shared, self.charge_b_shared], charges)

        # however, when u belongs to the same account as an existing bill,
        # and that bill meets the requirements to be its "predecessor",
        # un-shared RSIs from the "predecessor" of u also get included.
        self.utilbill_loader.reset_mock()
        self.u.customer.account = '10001'
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1, self.utilbill_2, self.utilbill_3]
        self.utilbill_loader.get_last_real_utilbill.side_effect = None
        self.utilbill_loader.get_last_real_utilbill.return_value = \
            self.utilbill_1
        charges = self.fpm.get_predicted_charges(self.u)
        self.utilbill_loader.load_real_utilbills.assert_has_calls([
            call(utility=self.utility, rate_class=self.rate_class,
                 processed=True),
            call(supplier=self.supplier, processed=True)])
        self.assertEqual([self.charge_a_shared, self.charge_b_shared,
                self.charge_c_unshared], charges)

    def test_missing_dates(self):
        """Test predicting charges for bills that have a missing start or
        end date or both.
        """
        self.utilbill_loader.get_last_real_utilbill.side_effect = \
            NoSuchBillException
        self.utilbill_loader.load_real_utilbills.return_value = [
            self.utilbill_1]

        # if no dates are known, no shared charges are generated
        self.u.period_start, self.u.period_end = None, None
        charges = self.fpm.get_predicted_charges(self.u)
        self.assertEqual([], charges)

        # if only one date is known, that's enough to guess the charges using an
        # estimate of the other date
        self.u.period_start, self.u.period_end = None, date(2000,2,1)
        self.assertEqual([self.charge_a_shared],
                         self.fpm.get_predicted_charges(self.u))
        self.u.period_start, self.u.period_end = date(2000,1,1), None
        self.assertEqual([self.charge_a_shared],
                         self.fpm.get_predicted_charges(self.u))

    def test_supply_distribution(self):
        """Test separate grouping of relevant bills for generating supply and
        distribution charges.
        """
        # each example bill has a shared charge of both types.
        # the relevant bills for distribution are utilbill_1 and utilbill_2,
        # even though utilbill_3 also has a distribution charge.
        # the relevant bills for supply are utilbill_2 and utilbill_3.
        # even though utilbill_1 also has a supply charge.
        # TODO: would be good to share some of this test data with the other
        # test methods if possible.
        d1 = Charge('d1', 0, '', type='distribution', shared=True)
        d2 = Charge('d2', 0, '', type='distribution', shared=True)
        d3 = Charge('d3', 0, '', type='distribution', shared=True)
        s1 = Charge('s1', 0, '', type='supply', shared=True)
        s2 = Charge('s2', 0, '', type='supply', shared=True)
        s3 = Charge('s3', 0, '', type='supply', shared=True)
        self.utilbill_1.charges = [d1, s1]
        self.utilbill_2.charges = [d2, s2]
        self.utilbill_3.charges = [d3, s3]

        # 1 bill with same rate class as the target and different supplier,
        # 1 with both same rate class and supplier, 1 with different rate
        # class and same supplier
        # NOTE call order has to be the one asserted below for this to work
        self.utilbill_loader.load_real_utilbills.side_effect = [
            [self.utilbill_1, self.utilbill_2],
            [self.utilbill_2, self.utilbill_3],
        ]
        # no predecessor bill, because "un-shared" charges are irrelevant here
        self.utilbill_loader.get_last_real_utilbill.side_effect = \
            NoSuchBillException

        charges = self.fpm.get_predicted_charges(self.u)

        self.utilbill_loader.load_real_utilbills.assert_has_calls([
            call(utility=self.utility, rate_class=self.rate_class,
                 processed=True),
            call(supplier=self.u.supplier, processed=True),
        ])

        d_charges = {c for c in charges if c.type == Charge.DISTRIBUTION}
        s_charges = {c for c in charges if c.type == Charge.SUPPLY}

        # d_charges has distribution charges of utilbill_1,2
        # and s_charges has supply charges of utilbill_2,3
        self.assertEqual({d1, d2}, d_charges)
        self.assertEqual({s2, s3}, s_charges)


    # TODO test that the bill whose charges are being generated is ignored when
    # collecting the set of bills to generate charges

    # TODO test that no supply charges are generated when supplier is missing,
    # no distribution charges are generated when utility/rate class is missing.
