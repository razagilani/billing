#!/usr/bin/python
import sys
import MySQLdb
import subprocess
from subprocess import Popen
from billing import mongo
from billing.processing import state
from billing.processing.db_objects import Customer, UtilBill, ReeBill
import uuid as UUID # uuid collides with locals so both module and locals are renamed

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
    'password': 'reebill-dev',
    'database': 'skyline_dev',
    'user': 'reebill-dev'
}


state_db = state.StateDB(statedb_config)
dao = mongo.ReebillDAO(billdb_config)
session = state_db.session()

for account in state_db.listAccounts(session):
    customer = session.query(Customer).filter(Customer.account == account).one()

    for sequence in state_db.listSequences(session, account):
        mongo_reebill = dao.load_reebill(account, sequence)

        for service in mongo_reebill.services:
            actual_chargegroups = mongo_reebill.actual_chargegroups_for_service(service)

            for (chargegroup, charges) in actual_chargegroups.iteritems():
                for charge in charges:
                    if 'uuid' in charge:
                        print "has uuid %s" % charge['uuid']
                    else:
                        print "no uuid %s" % charge
                        charge['uuid'] = str(UUID.uuid1())
            mongo_reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)

            hypothetical_chargegroups = mongo_reebill.hypothetical_chargegroups_for_service(service)

            for (chargegroup, charges) in hypothetical_chargegroups.iteritems():
                for charge in charges:
                    if 'uuid' in charge:
                        print "has uuid %s" % charge['uuid']
                    else:
                        print "no uuid %s" % charge
                        charge['uuid'] = str(UUID.uuid1())
            mongo_reebill.set_hypothetical_chargegroups_for_service(service, hypothetical_chargegroups)

        dao.save_reebill(mongo_reebill)



# commit changes
session.commit()
