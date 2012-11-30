'''Tests for rate_structure.py'''
import unittest
import pymongo
import MySQLdb
import sqlalchemy
from billing.processing import rate_structure
from billing.processing.db_objects import Customer
from billing.processing.state import StateDB
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

    def test_load_rate_structure(self):
        '''Tests loading the "probable RS" by combining the URS, UPRS, and CPRS
        rate structure documents.'''
        account, sequence = '99999', 1

        # get RS docs and put them in mongo
        urs_dict = example_data.get_urs_dict()
        uprs_dict = example_data.get_uprs_dict()
        cprs_dict = example_data.get_cprs_dict(account, sequence)
        self.rate_structure_dao.save_urs(urs_dict['_id']['utility_name'],
                # 'effective', 'expires' args are ignored
                urs_dict['_id']['rate_structure_name'], None, None, urs_dict)
        self.rate_structure_dao.save_uprs(uprs_dict['_id']['utility_name'],
                # 'effective', 'expires' args are ignored
                uprs_dict['_id']['rate_structure_name'], None, None, uprs_dict)
        self.rate_structure_dao.save_cprs(account, sequence, 0,
                cprs_dict['_id']['utility_name'],
                cprs_dict['_id']['rate_structure_name'], cprs_dict)

        # get reebill doc and put it in mongo, load it back out to get a
        # MongoReebill object
        self.reebill_dao.save_reebill(example_data.get_reebill(account, sequence))
        # save reebill in in mysql; reebill_dao needs that to get max_version
        # for loading
        with DBSession(self.state_db) as session:
            self.state_db.new_rebill(session, account, sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # load probable rate structure
        prob_rs = self.rate_structure_dao._load_combined_rs_dict(reebill,
                reebill.services[0])

        # each RSI in the probable rate structure should match the version in
        # the "highest-level" rate structure document in which a rate structure
        # with the same rsi_binding appears
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
