'''Tests for rate_structure.py'''
from datetime import date
from StringIO import StringIO
import unittest
from mock import Mock
from bson import ObjectId
from mongoengine import DoesNotExist
from billing.processing.rate_structure2 import RateStructure, \
    RateStructureItem, RateStructureDAO
from billing.processing.state import StateDB, Customer, UtilBill
from billing.test.setup_teardown import TestCaseWithSetup
from billing.util.dictutils import deep_map, subdict
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import FormulaError, FormulaSyntaxError

def compare_rsis(rsi1, rsi2):
    '''Compares two Rate Structure Item dictionaries, ignoring differences
    between ascii and unicode strings, and only considering a subset of
    keys. Returns True if they are equal.'''
    def str_to_unicode(x):
        return unicode(x) if isinstance(x, str) else x
    keys = ["rate", "rsi_binding", "roundrule", "quantity"]
    return deep_map(str_to_unicode, subdict(rsi1, keys)) == \
            deep_map(str_to_unicode, subdict(rsi2, keys))

class RateStructureDAOTest(TestCaseWithSetup):

    # TODO convert this to a real "unit test" (testing RateStructureDAO in
    # isolation) or move it into test_process.py
    @unittest.skip('Not relevant to rate_structure2')
    def test_load_rate_structure(self):
        '''Tests loading the "probable RS" by combining the URS, UPRS, and CPRS
        rate structure documents.'''
        account, sequence = '99999', 1

        with DBSession(self.state_db) as session:
            # make a utility bill
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2012,1,1), date(2012,2,1), StringIO('January 2012'),
                    'january.pdf', utility='washgas',
                    rate_class='DC Non Residential Non Heat')
            utilbill = session.query(UtilBill).one()

            # get RS docs and put them in mongo
            urs_dict = self.rate_structure_dao.load_urs(utilbill.utility,
                    utilbill.rate_class)
            uprs_dict = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
            cprs_dict = self.rate_structure_dao.load_cprs_for_utilbill(utilbill)

            # load probable rate structure
            prob_rs = self.rate_structure_dao._load_combined_rs_dict(utilbill)

            # each RSI in the probable rate structure should match the version
            # of that RSI in the "highest-level" rate structure document in
            # which it appears (where two RSIs are considered the same if they
            # have the same 'rsi_binding')
            for rsi in prob_rs['rates']:
                binding = rsi['rsi_binding']
                # if a RSI with this binding is in the CPRS, it must match the CPRS'
                # version exactly
                cprs_matches = [r for r in cprs_dict['rates'] if
                        r['rsi_binding'] == binding]
                if cprs_matches != []:
                    assert len(cprs_matches) == 1
                    self.assertTrue(compare_rsis(cprs_matches[0], rsi))
                    continue

                # no RSI with this binding is in the CPRS, so look in the UPRS
                uprs_matches = [r for r in uprs_dict['rates'] if
                        r['rsi_binding'] == binding]
                if uprs_matches != []:
                    assert len(uprs_matches) == 1
                    self.assertTrue(compare_rsis(uprs_matches[0], rsi))
                    continue

                # if the RSI is not in either the CPRS or the UPRS, it must be in
                # the URS
                urs_matches = [r for r in urs_dict['rates'] if
                        r['rsi_binding'] == binding]
                assert len(urs_matches) == 1
                self.assertTrue(compare_rsis(urs_matches[0], rsi))

class RSITest(unittest.TestCase):
    def setUp(self):
        pass

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
        self.uprs = RateStructure(type='UPRS', rates=[self.a, self.b_1])
        self.cprs = RateStructure(type='CPRS', rates=[self.b_2, self.c])

    def test_combine(self):
        # 2nd RateStructure overrides the first, so b_2 is in the combination
        # (note that order of RSIs within a RateStructure does not matter,
        # so they are compared as sets)
        result = RateStructure.combine(self.uprs, self.cprs)
        self.assertEqual(set([self.a, self.b_2, self.c]), set(result.rates))

        # if the order of the arguments is reversed, b_1 is in the combination
        result = RateStructure.combine(self.cprs, self.uprs)
        self.assertEqual(set([self.a, self.b_1, self.c]), set(result.rates))

    def test_add_rsi(self):
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
        self.assertEqual(set([self.a, self.b_1, new_rsi_1]),
                set(self.uprs.rates))
        self.uprs.add_rsi()
        self.assertEqual(set([self.a, self.b_1, new_rsi_1, new_rsi_2]),
                set(self.uprs.rates))

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
        )
        self.rsi_b_shared = RateStructureItem(
            rsi_binding='B',
            quantity='2',
            rate='2',
            shared=True,
        )
        self.rsi_b_unshared = RateStructureItem(
            rsi_binding='B',
            quantity='2',
            rate='2',
            shared=False,
        )

        # 3 rate structures, one containing B shared and one containing B
        # unshared. If unshared RSIs count as "absent", B is more absent than
        # present and should be excluded from a new predicted rate structure.
        # If unshared RSIs count as neutral, B shared occurs 1 out of 1 times,
        # so it should be included in a new predicted rate structure.
        self.rs_1 = RateStructure(id=ObjectId(), rates=[self.rsi_a_shared,
                self.rsi_b_unshared])
        self.rs_2 = RateStructure(id=ObjectId(), rates=[self.rsi_b_unshared])
        self.rs_3 = RateStructure(id=ObjectId(), rates=[self.rsi_b_shared])

        self.utilbill_1 = Mock()
        self.utilbill_1.uprs_document_id = str(self.rs_1.id)
        self.utilbill_1.period_start = date(2000,1,1)
        self.utilbill_1.period_end = date(2000,2,1)

        self.utilbill_2 = Mock()
        self.utilbill_2.uprs_document_id = str(self.rs_2.id)
        self.utilbill_2.period_start = date(2000,1,1)
        self.utilbill_2.period_end = date(2000,2,1)

        self.utilbill_3 = Mock()
        self.utilbill_3.period_start = date(2000,1,1)
        self.utilbill_3.period_end = date(2000,2,1)
        self.utilbill_3.uprs_document_id = str(self.rs_3.id)

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
            objects = MockQuerySet(self.rs_1, self.rs_2)

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

    def test_get_probable_uprs(self):
        utilbill_loader = Mock()
        utilbill_loader.load_real_utilbills.return_value = [self.utilbill_1,
            self.utilbill_2]

        uprs = self.dao.get_probable_uprs(utilbill_loader, 'washgas', 'gas',
                'DC Non Residential Non Heat', date(2000,1,1), date(2001,2,1))

        # see explanation in setUp for why rsi_a_shared and rsi_b_shared
        # should be included here
        self.assertEqual([self.rsi_a_shared, self.rsi_b_shared], uprs.rates)

if __name__ == '__main__':
    unittest.main(failfast=True)
