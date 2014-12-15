import MySQLdb
import os
import sys
import re
import shutil
import argparse
from billing.processing.state import StateDB, UtilBill, Customer
from datetime import date, timedelta
from sqlalchemy.orm.exc import NoResultFound

DATETOLERANCE=10 # if no exact match could be found search a bill starting/ending within +-X days

# command-line arguments
parser = argparse.ArgumentParser(description='05_rename_utilbills')
parser.add_argument('--statedbhost', required=True)
parser.add_argument('--statedbname', required=True)
parser.add_argument('--statedbuser', required=True)
parser.add_argument('--statedbpasswd', required=True)
parser.add_argument('--utilitybillpath', required=True)
args = parser.parse_args()

sdb = StateDB(**{
    'host': args.statedbhost,
    'database': args.statedbname,
    'user': args.statedbuser,
    'password': args.statedbpasswd
})

utilbillpath=args.utilitybillpath

s = sdb.session()
pattern=re.compile('^(\d{4})(\d{2})(\d{2})-(\d{4})(\d{2})(\d{2}).pdf')

for x in os.walk(utilbillpath):
    account=os.path.basename(x[0])
    for file_name in x[2]:
        m = pattern.match(file_name)
        if m:
            try:
                start= date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
            except ValueError:
                print 'Invalid date in filename ',file_name
                continue
            try:
                q = s.query(UtilBill.id).join(Customer).filter(
                    Customer.account == account,
                    UtilBill.period_end == end,
                    UtilBill.period_start == start
                ).one()
            except NoResultFound:
                print 'No Utilbill found for ',account,' starting ', start,', ending ', end
                try:
                    tolerance=timedelta(days=DATETOLERANCE)
                    q = s.query(UtilBill.id).join(Customer).filter(
                        Customer.account == account,
                        UtilBill.period_end >= (end-tolerance),
                        UtilBill.period_end <= (end+tolerance),
                        UtilBill.period_start >= (start-tolerance),
                        UtilBill.period_start <= (start+tolerance)
                    ).one()
                    print '---> Assuming bill ', q[0]
                except NoResultFound:
                    continue
            shutil.copy(
                os.path.join(utilbillpath,account,file_name),
                os.path.join(utilbillpath,account,str(q[0])+'.pdf')
            )
