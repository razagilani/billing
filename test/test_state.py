#!/usr/bin/python
import unittest
from billing.processing import state
from billing import mongo
from billing import dateutils

statedb_config = {'user':'dev', 'password':'dev', 'host':'localhost', 'database':'skyline_dev'}
billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateTest(unittest.TestCase):
    def setUp(self):
        self.state_db = state.StateDB(**statedb_config)
        self.reebill_dao = mongo.ReebillDAO(billdb_config)

    def test_guess_next_reebill_end_date(self):
        '''Compare real end date to the one that would have been prediected.'''
        total = 0
        count = 0
        correct_count = 0
        session = self.state_db.session()
        for account in self.state_db.listAccounts(session):
            for sequence in self.state_db.listSequences(session, account):
                try:
                    reebill = self.reebill_dao.load_reebill(account, sequence)
                    guessed_end_date = state.guess_next_reebill_end_date(session, account, reebill.period_begin)
                    difference = abs(reebill.period_end - guessed_end_date).days
                    total += difference
                    count += 1
                    if difference == 0:
                        correct_count += 1
                except Exception as e:
                    # TODO don't bury this error
                    print '%s-%s ERROR' % (account, sequence)
        print 'average difference: %s days' % (total / float(count))
        print 'guessed correctly: %s%%' % (100 * correct_count / float(count))
        
        # if we're right 95% of the time, guess_next_reebill_end_date() works
        self.assertTrue(correct_count / float(count) > .95)
        session.commit()

if __name__ == '__main__':
    unittest.main()
