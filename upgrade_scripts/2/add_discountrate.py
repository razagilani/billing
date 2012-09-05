#!/usr/bin/python
'''This script copies each customer's discount rate from MySQL and puts it into
Mongo. Make sure to set the config parameters with "dev" in them to "prod"
before running on tyrell.'''
import traceback
from decimal import Decimal
from billing import mongo
from billing.processing import state
from billing.processing.db_objects import Customer

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}
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
    discount_rate = session.query(Customer).filter(Customer.account==account).one().discountrate
    sequences = state_db.listSequences(session, account)
    for sequence in sequences:
        print '%s-%s: %s' % (account, sequence, Decimal(str(discount_rate)))
        try:
            reebill = reebill_dao.load_reebill(account, sequence)
            reebill.discount_rate = Decimal(str(discount_rate))
            reebill_dao.save_reebill(reebill)
        except Exception as e:
            print e, traceback.format_exc()
