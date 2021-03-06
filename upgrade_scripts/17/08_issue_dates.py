from sys import stderr
import MySQLdb
import pymongo

mysql_host = 'localhost'
mysql_user = 'root'
mysql_pass = 'root'
mysql_db = 'skyline_dev'
mongo_host = 'localhost'
mongo_db = 'skyline-dev'

mysql_con = MySQLdb.Connection(mysql_host, mysql_user, mysql_pass, mysql_db)
mysql_cur = mysql_con.cursor()
mongo_db = pymongo.Connection(mongo_host)[mongo_db]

mysql_cur.execute('''alter table reebill add column issue_date date''')
mysql_cur.execute('''select reebill.id, reebill.issued, customer.account, reebill.sequence, reebill.version from reebill join customer on reebill.customer_id = customer.id''')
for row in mysql_cur.fetchall():
    reebill_id, issued, account, sequence, version = row
    mongo_reebill = mongo_db.reebills.find_one({'_id.account':account, '_id.sequence':sequence, '_id.version':version})
    issue_date = mongo_reebill['issue_date']
    if issued > 0:
        if issue_date is None:
            print >> stderr, "Issue date is missing for issued reebill %s-%s-%s" %(account, sequence, version)
        else:
            sql_str = 'update reebill set issue_date = date("%s") where reebill.id = %s' %(mongo_reebill['issue_date'].date().isoformat(), reebill_id)
            mysql_cur.execute(sql_str)
            #print "set reebill with id %s to issue_date %s" \
            #    %(reebill_id, mongo_reebill['issue_date'])

mysql_con.commit()
