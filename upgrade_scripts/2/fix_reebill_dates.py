#!/usr/bin/python
'''This script replaces all reebill dates that are null/None with the correct
dates taken from their utilbills.'''
import traceback
from billing import mongo
from billing.processing import state

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}
statedb_config = {
    'host': 'localhost',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev'
}

reebill_dao = mongo.ReebillDAO(billdb_config)
state_db = state.StateDB(statedb_config)

session = state_db.session()
accounts = state_db.listAccounts(session)

print sorted(accounts)
exit()
for account in accounts:
    sequences = state_db.listSequences(session, account)
    for sequence in sequences:
        try:
            reebill = reebill_dao.load_reebill(account, sequence)
            print account, sequence, reebill.period_begin, reebill.period_end
            if reebill.period_begin is None:
                reebill.period_begin = min(p[0] for p in
                        (reebill.utilbill_period_for_service(s) for s in
                        reebill.services))
                reebill_dao.save_reebill(reebill)
                print '%s-%s begin fixed' % (account, sequence)
            if reebill.period_end is None:
                reebill.period_end = max(p[1] for p in
                        (reebill.utilbill_period_for_service(s) for s in
                        reebill.services))
                reebill_dao.save_reebill(reebill)
                print '%s-%s end fixed' % (account, sequence)
        except Exception as e:
            print '%s-%s: %s\n%s' % (account, sequence, e, traceback.format_exc())
