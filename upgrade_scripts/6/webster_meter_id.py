#!/usr/bin/python
import sys
import subprocess
from billing import mongo
from billing.processing import state
from billing.processing.db_objects import Customer, UtilBill, ReeBill
import uuid as UUID # uuid collides with locals so both module and locals are renamed
'''Set meter identifier for 10019/Webster House to "Z42421" (currently the
meter has identifier "P87210" in all reebills).'''

# remember to set db parameters for staging/production before running
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
state_db = state.StateDB(**statedb_config)
dao = mongo.ReebillDAO(billdb_config)
session = state_db.session()

account = '10019'
# include sequence 0
for sequence in [0] + state_db.listSequences(session, account):
    reebill = dao.load_reebill(account, sequence)
    for service in reebill.services:
        reebill.set_meter_identifier(service, 'P87210', 'Z42421')
    dao.save_reebill(reebill)

session.commit()

