#!/usr/bin/python
import sys
import MySQLdb
import subprocess
from subprocess import Popen
from billing import mongo
from billing.processing import state
from billing.processing.db_objects import Customer, UtilBill, ReeBill

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


#db, user, password = 'skyline_dev', 'dev', 'dev'
#sql = 'alter table utilbill add service varchar(45)'
#mysql_process = Popen(('mysql -u%s -p%s' % (statedb_config['user'],
    #statedb_config['password'])).split(), stdin=subprocess.PIPE,
    #stdout=subprocess.PIPE)
#out, err = mysql_process.communicate('use %s; %s; quit;' % (db, sql))
#print out, err

conn = MySQLdb.connect(host='localhost', db=statedb_config['database'],
        user=statedb_config['user'], passwd=statedb_config['password'])
cursor = conn.cursor()

# create service column in utilbill table
# NOTE will fail if column is already present: script can only run once
cursor.execute('alter table utilbill add service varchar(45)')

state_db = state.StateDB(statedb_config)
dao = mongo.ReebillDAO(billdb_config)
session = state_db.session()

## check that 10001 multi-service bill is ok
#reebill = dao.load_reebill('10001', 2)
#for service in reebill.services:
    #print service, reebill.utilbill_period_for_service(service)
#exit()

earliest_mongo_utilbill_dates = {}

for account in state_db.listAccounts(session):
    customer = session.query(Customer).filter(Customer.account == account).one()

    for sequence in state_db.listSequences(session, account):

        # load reebill representations from both databases
        mongo_reebill = dao.load_reebill(account, sequence)
        mysql_reebill = session.query(ReeBill)\
                .filter(ReeBill.customer_id == customer.id)\
                .filter(ReeBill.sequence == sequence).one()

        for service in mongo_reebill.services:
            start, end = mongo_reebill.utilbill_period_for_service(service)
            query = session.query(UtilBill)\
                    .filter(UtilBill.customer_id == customer.id)\
                    .filter(UtilBill.period_start == start)\
                    .filter(UtilBill.period_end == end)
            matching_utilbills = list(query)
            if matching_utilbills == []:
                # TODO some reebills, e.g. 10001-2, seem to be missing mysql
                # entries for the utilbills listed in mongo
                print >> sys.stderr, '%s-%s ERROR: no utilbill in mysql for period %s - %s' % (
                        account, sequence, start, end)
            elif len(matching_utilbills) > 1:
                # if multiple utilbills match the dates, we don't know which
                # one is which service. luckly this has not happened yet.
                print >> sys.stderr, '%s-%s ERROR: multiple utilbills in mysql have period %s - %s' % (
                        account, sequence, start, end)
            else:
                # exactly one utilbill matches--we know what its service is so put it in
                utilbill = matching_utilbills[0]
                print '%s-%s %s - %s: %s' % (account, sequence, start, end, service.lower())
                utilbill.service = service.lower()

        earliest_utilbill_start = min(mongo_reebill.\
                utilbill_period_for_service(service) for service in
                mongo_reebill.services)[0]
        if account not in earliest_mongo_utilbill_dates:
            earliest_mongo_utilbill_dates[account] = earliest_utilbill_start
        elif earliest_utilbill_start < earliest_mongo_utilbill_dates[account]:
            earliest_mongo_utilbill_dates[account] = earliest_utilbill_start

# commit changes
session.commit()
session = state_db.session()

#print '\n'.join(('%s: %s' % (acc, day) for acc, day in sorted(earliest_mongo_utilbill_dates.iteritems())))
null_service_utilbills = session.query(UtilBill).filter(UtilBill.service == None).all()
print '\n--------------------------------------'
print 'Utility bills with NULL service:'
for ub in null_service_utilbills:
    if ub.customer is None:
        print 'ERROR utilbill %s has null customer id!' % ub
    elif ub.customer.account not in earliest_mongo_utilbill_dates:
        if ub.customer.account == '10015':
            print ub, "for account 10015 has no utilbills in Mongo yet, but we know it's 'gas'"
            ub.service = 'gas'
        else:
            print 'ERROR account %s has no utilbills in mongo!' % ub.customer.account
    elif ub.period_end <= earliest_mongo_utilbill_dates[account]:
        earliest_reebill_services = dao.load_reebill(ub.customer.account, 1).services
        if len(earliest_reebill_services) == 0:
            print ub.customer.account, ub.period_start, ub.period_end,\
                    "is OK, but can't add service because earliest reebill has multiple services; it will remain NULL"
        else:
            print ub.customer.account, ub.period_start, ub.period_end,\
                    "is OK: filled in service", earliest_reebill_services[0].lower()
            ub.service = earliest_reebill_services[0].lower()
    else:
        print ub, 'ERROR: does not match anything in Mongo'
session.commit()
