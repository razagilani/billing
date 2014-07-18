'''Tests for rate_structure.py'''
from datetime import date
import unittest
from mock import Mock
from bson import ObjectId
from mongoengine import DoesNotExist
from billing.processing.rate_structure2 import RateStructure, \
    RateStructureItem, RateStructureDAO
from billing.processing.exceptions import FormulaError, FormulaSyntaxError, \
    NoSuchBillException

class RSITest(unittest.TestCase):

    def test_basic(self):
        a = RateStructureItem(
            rsi_binding='A',
            quantity='1',
            quantity_units='dollars',
            rate='1',
        )

        self.assertEqual({
             'id': 'A',
             'rsi_binding':'A',
             'description': '',
             'quantity':'1',
             'quantity_units':'dollars',
             'rate':'1',
             'has_charge': True,
             'group': '',
             'round_rule': None,
             'shared': True,
         }, a.to_dict())

        a.update()
        self.assertEqual(RateStructureItem(
            rsi_binding='A',
            quantity='1',
            quantity_units='dollars',
            rate='1',
        ), a)

        a.update(quantity='10', rate='11')
        self.assertEqual(RateStructureItem(
            rsi_binding='A',
            quantity='10',
            quantity_units='dollars',
            rate='11',
        ), a)

        self.assertRaises(TypeError, a.update, 'A', nonexistent_field=1)

    def test_load_malformed_document(self):
        '''Test creating RateStructureItem object from malformed Mongo
        document.
        '''
        # the main malformation we have seen so far is old documents where
        # the "quantity" or "rate" formula was missing or an empty string.
        # these are now required to have a value, and the default should be 0.
        a = RateStructureItem._from_son({
            'quantity': '1',
            'rate': '',
        })
        self.assertEqual('0', a.rate)
        b = RateStructureItem._from_son({
            'quantity': '',
            'rate': '1',
        })
        self.assertEqual('0', b.quantity)

    def test_compute_charge_basic(self):
        rsi = RateStructureItem(
            rsi_binding='A',
            quantity='R1.rate + 2',
            quantity_units='therms',
            # division included to make sure "future" (i.e. float) division
            # is being used, so 3/4 = .75, not 0
            rate='3 / 4 - R2.quantity',
        )
        quantity, rate = rsi.compute_charge({
            'R1': { 'quantity': 2, 'rate': 1, },
            'R2': { 'quantity': 0.5, 'rate': 10, }
        })
        self.assertEqual(3, quantity)
        self.assertEqual(0.25, rate)

    def test_compute_charge_errors(self):
        bad_rsi = RateStructureItem(
            rsi_binding='A',
            quantity='1 + &',
            quantity_units='therms',
            rate='0',
        )
        # invalid syntax: FormulaSyntaxError
        self.assertRaises(FormulaSyntaxError, bad_rsi.compute_charge, {})

        # unknown identifier: generic FormulaError
        bad_rsi.quantity = '1 + x.quantity'
        self.assertRaises(FormulaError, bad_rsi.compute_charge, {})

        # quantity formula can't be empty
        bad_rsi.quantity = ''
        with self.assertRaises(FormulaSyntaxError) as context:
            bad_rsi.compute_charge({})
        self.assertEqual("A quantity formula can't be empty",
                context.exception.message)

        # rate formula can't be empty
        bad_rsi.quantity = '1'
        bad_rsi.rate = ''
        with self.assertRaises(FormulaSyntaxError) as e:
                bad_rsi.compute_charge({})
        self.assertEqual("A quantity formula can't be empty",
                context.exception.message)

class RateStructureTest(unittest.TestCase):

    def setUp(self):
        self.a = RateStructureItem(
            rsi_binding='A',
            quantity='1',
            quantity_units='dollars',
            rate='1',
        )
        self.b_1 = RateStructureItem(
            rsi_binding='B',
            quantity='2',
            quantity_units='kWh',
            rate='2',
        )
        self.b_2 = RateStructureItem(
            rsi_binding='B',
            quantity='3',
            quantity_units='therms',
            rate='3',
        )
        self.c = RateStructureItem(
            rsi_binding='C',
            quantity='4',
            quantity_units='therms',
            rate='4',
        )
        self.uprs = RateStructure(rates=[self.a, self.b_1])

    def test_combine(self):
        # 2nd RateStructure overrides the first, so b_2 is in the combination
        # (note that order of RSIs within a RateStructure does not matter,
        # so they are compared as sets)
        other_rs = RateStructure(rates=[self.b_2, self.c])
        result = RateStructure.combine(self.uprs, other_rs)
        self.assertEqual(set([self.a, self.b_2, self.c]), set(result.rates))

        # if the order of the arguments is reversed, b_1 is in the combination
        result = RateStructure.combine(other_rs, self.uprs)
        self.assertEqual(set([self.a, self.b_1, self.c]), set(result.rates))

    def test_add_update_rsi(self):
        new_rsi_1 = RateStructureItem(
            rsi_binding='New RSI #1',
            description='Insert description here',
            quantity='0',
            quantity_units='',
            rate='0',
            round_rule='',
        )
        new_rsi_2 = RateStructureItem(
            rsi_binding='New RSI #2',
            description='Insert description here',
            quantity='0',
            quantity_units='',
            rate='0',
            round_rule='',
        )
        self.uprs.add_rsi()
        self.assertEqual([self.a, self.b_1, new_rsi_1], self.uprs.rates)
        self.uprs.add_rsi()
        self.assertEqual([self.a, self.b_1, new_rsi_1, new_rsi_2],
                self.uprs.rates)

    def test_validate(self):
        self.uprs.rates.append(self.a)
        self.assertRaises(ValueError, self.uprs.validate)

class RateStructureDAOTest(unittest.TestCase):
    def setUp(self):
        self.rsi_a_shared = RateStructureItem(
            rsi_binding='A',
            quantity='1',
            rate='1',
            shared=True,
            group='a',
            has_charge=True,
        )
        self.rsi_b_shared = RateStructureItem(
            rsi_binding='B',
            quantity='2',
            rate='2',
            shared=True,
            group='b',
            has_charge=True,
        )
        self.rsi_b_unshared = RateStructureItem(
            rsi_binding='B',
            quantity='2',
            rate='2',
            shared=False,
            group='c',
            has_charge=False,
        )
        self.rsi_c_unshared = RateStructureItem(
            rsi_binding='C',
            quantity='3',
            rate='3',
            shared=False,
            group='d',
            has_charge=False,
        )

        # 3 rate structures, two containing B shared and one containing B
        # unshared. If unshared RSIs count as "absent", B is more absent than
        # present and should be excluded from a new predicted rate structure.
        # If unshared RSIs count as neutral, B shared occurs 1 out of 1 times,
        # so it should be included in a new predicted rate structure. C is
        # never shared so it never gets included in any bill, except one
        # whose "predecessor" contains it.
        self.rs_1 = RateStructure(id=ObjectId(), rates=[
            self.rsi_a_shared,
            self.rsi_b_unshared,
            self.rsi_c_unshared,
        ])
        self.rs_2 = RateStructure(id=ObjectId(), rates=[
            self.rsi_a_shared,
            self.rsi_b_unshared
        ])
        self.rs_3 = RateStructure(id=ObjectId(), rates=[self.rsi_b_shared])

        def make_mock_utilbill(account, rs):
            u = Mock()
            u.customer.account = account
            u.uprs_document_id = str(rs.id)
            u.period_start = date(2000,1,1)
            u.period_end = date(2000,2,1)
            u.processed = False
            u.service = 'gas'
            u.utility = 'washgas'
            u.rate_class = 'whatever'
            return u
        self.utilbill_1 = make_mock_utilbill('00001', self.rs_1)
        self.utilbill_2 = make_mock_utilbill('00002', self.rs_2)
        self.utilbill_3 = make_mock_utilbill('00003', self.rs_3)

        class MockQuerySet(object):
            def __init__(self, *documents):
                self._documents = documents

            def get(self, **kwargs):
                document_subset = [d for d in self._documents
                    if all(hasattr(d, k) and getattr(d, k) == v
                        for k, v in kwargs.iteritems())]
                # return MockQuerySet(*document_subset)

                if len(document_subset) == 0:
                    raise DoesNotExist
                if len(document_subset) > 1:
                    raise MockRateStructure.MultipleObjectsReturned
                return document_subset[0]

        class MockRateStructure(object):
            objects = MockQuerySet(self.rs_1, self.rs_2, self.rs_3)

            # in MongoEngine, each class has its own MultipleObjectsReturned
            # exception
            class MultipleObjectsReturned(Exception):
                pass

            def save(self):
                # TODO
                raise NotImplementedError

            def delete(self):
                # TODO
                raise NotImplementedError

        self.dao = RateStructureDAO(rate_structure_class=MockRateStructure)


    def test_load_uprs_for_utilbill(self):
        self.assertEqual(self.rs_1,
                self.dao.load_uprs_for_utilbill(self .utilbill_1))
        self.assertEqual(self.rs_2,
                self.dao.load_uprs_for_utilbill(self .utilbill_2))

        unknown_utilbill = Mock()
        unknown_utilbill.uprs_document_id = '3'*24
        self.assertRaises(DoesNotExist, self.dao.load_uprs_for_utilbill,
                unknown_utilbill)

    def test_get_predicted_rate_structure(self):
        utilbill_loader = Mock()

        # utility bill for which to predict a rate structure, using the
        # ones created in setUp
        u = Mock()
        u.customer.account = '00004'
        u.period_start = date(2000,1,1)
        u.period_end = date(2000,2,1)
        u.processed = False
        u.service = 'gas'
        u.utility = 'washgas'
        u.rate_class = 'whatever'
        # arbitrary 24-digit string
        u.uprs_document_id = ''.join(str(i % 10) for i in xrange(24))

        # with no processed utility bills, predicted rate structure is empty.
        # note that since 'utilbill_loader' is used, actually loading the
        # utility bills with the given attributes is outside the scope of
        # RateStructureDAO
        def raise_nsbe(*args, **kwargs):
            raise NoSuchBillException
        utilbill_loader.get_last_real_utilbill.side_effect = raise_nsbe
        utilbill_loader.load_real_utilbills.return_value = []
        rs = self.dao.get_predicted_rate_structure(u,
                utilbill_loader)
        utilbill_loader.get_last_real_utilbill.assert_called_once_with(
                u.customer.account, u.period_start,
                service=u.service, utility=u.utility,
                rate_class=u.rate_class, processed=True)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([], rs.rates)

        # with only the 1st utility bill (containing rsi_a_shared and
        # rsi_b_unshared), only rsi_a_shared should appear in the result
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1]
        rs = self.dao.get_predicted_rate_structure(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.rsi_a_shared], rs.rates)

        # with 2 existing utility bills processed, predicted rate structure
        # includes both A (shared) and B (shared)
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        rs = self.dao.get_predicted_rate_structure(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.rsi_a_shared, self.rsi_b_shared], rs.rates)

        # with 3 processed utility bills
        utilbill_loader.reset_mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        uprs = self.dao.get_predicted_rate_structure(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        # see explanation in setUp for why rsi_a_shared and rsi_b_shared
        # should be included here
        self.assertEqual([self.rsi_a_shared, self.rsi_b_shared], uprs.rates)

        # the same is true when the period of 'u' starts after the period of
        # the existing bills
        utilbill_loader.reset_mock()
        u.period_start, u.period_end = date(2000,2,1), date(2000,3,1)
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                self.utilbill_2, self.utilbill_3]
        rs = self.dao.get_predicted_rate_structure(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.rsi_a_shared, self.rsi_b_shared], rs.rates)

        # however, when u belongs to the same account as an existing bill,
        # and that bill meets the requirements to be its "predecessor",
        # un-shared RSIs from the "predecessor" of u also get included.
        utilbill_loader.reset_mock()
        u.customer.account = '10001'
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
                                            self.utilbill_2, self.utilbill_3]
        utilbill_loader.get_last_real_utilbill.side_effect = None
        utilbill_loader.get_last_real_utilbill.return_value = self.utilbill_1
        rs = self.dao.get_predicted_rate_structure(u, utilbill_loader)
        utilbill_loader.load_real_utilbills.assert_called_once_with(
                service='gas', utility='washgas', rate_class='whatever',
                processed=True)
        self.assertEqual([self.rsi_a_shared, self.rsi_b_shared,
                self.rsi_c_unshared], rs.rates)


    # TODO test that RS of the bill being predicted is ignored, whether or not
    # that RS exists in the db yet

if __name__ == '__main__':
    unittest.main(failfast=True)
