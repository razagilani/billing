'''Tests for rate_structure.py'''
from datetime import date
from StringIO import StringIO
import unittest
import pymongo
import MySQLdb
import sqlalchemy
from billing.processing import rate_structure2
from billing.processing.state import StateDB, Customer, UtilBill
from billing.processing import mongo
from billing.test import example_data
from billing.test.setup_teardown import TestCaseWithSetup
from billing.util.dictutils import deep_map, subdict
from billing.processing.session_contextmanager import DBSession

def compare_rsis(rsi1, rsi2):
    '''Compares two Rate Structure Item dictionaries, ignoring differences
    between ascii and unicode strings, and only considering a subset of
    keys. Returns True if they are equal.'''
    def str_to_unicode(x):
        return unicode(x) if isinstance(x, str) else x
    keys = ["rate", "rsi_binding", "roundrule", "quantity"]
    return deep_map(str_to_unicode, subdict(rsi1, keys)) == \
            deep_map(str_to_unicode, subdict(rsi2, keys))

class RateStructureTest(TestCaseWithSetup):

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

if __name__ == '__main__':
    unittest.main(failfast=True)
