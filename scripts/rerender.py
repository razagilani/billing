#!/usr/bin/python
import traceback
from billing import mongo
from billing.reebill import render
from billing.processing import state

billdb_config = ({
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
})
statedb_config = {
    'host': 'tyrell',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev'
}
reebill_dao = mongo.ReebillDAO(billdb_config)
state_db = state.StateDB(statedb_config)

session = state_db.session()
accounts = state_db.listAccounts(session)

for account in accounts:
    sequences = state_db.listSequences(session, account)
    for sequence in sequences:
        print '%s-%s' % (account, sequence)
        try:
            reebill = reebill_dao.load_reebill(account, sequence)
            render.render(
                reebill, 
                billdb_config["billpath"]+ "%s/%.4d.pdf" % (account, int(sequence)),
                "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                None,
            )
        except Exception as e:
            print e, traceback.format_exc()
