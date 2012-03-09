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

# create utilbill
cursor.execute('alter table utilbill add service varchar(45)')

state_db = state.StateDB(statedb_config)
dao = mongo.ReebillDAO(billdb_config)
session = state_db.session()

## check that 10001 multi-service bill is ok
#reebill = dao.load_reebill('10001', 2)
#for service in reebill.services:
    #print service, reebill.utilbill_period_for_service(service)
#exit()

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
                print '%s-%s %s - %s: %s' % (account, sequence, start, end, service)
                utilbill.service = service

# commit changes
session.commit()

