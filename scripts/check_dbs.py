#This script checks the consistancy of the mongo database against the mysql database.
#
#Set this to True to issue warnings about sequence 0 reebills being ignored
print_ignores = False

import pymongo
import bson
import sqlalchemy

from collections import OrderedDict
from datetime import date,datetime
from sqlalchemy import orm
from sqlalchemy.orm import session
from sys import stdout, stderr

host = 'localhost'
db = 'skyline-dev' # mongo
statedb = 'skyline_dev' # mysql
user = 'dev'
password = 'dev'

#Create the mongo connection
mongodb = pymongo.Connection(host, 27017)[db]

#Start the sql session
engine = sqlalchemy.create_engine('mysql://%s:%s@%s:3306/%s' % (user, password, host, statedb), pool_recycle=3600, pool_size=5)
metadata = sqlalchemy.MetaData(engine)
utilbill_table = sqlalchemy.Table('utilbill', metadata, autoload=True)
reebill_table = sqlalchemy.Table('rebill', metadata, autoload=True)
customer_table = sqlalchemy.Table('customer', metadata, autoload=True)
session_class = orm.sessionmaker(bind=engine, autoflush=True)
session = session_class()

#Lists of columns
Utilbill = utilbill_table.c
Reebill = reebill_table.c
Customer = customer_table.c

#Mongo is in datetime, sql is in date
def datetime_to_date(dt):
    if (dt.hour != 0 or dt.minute != 0 or dt.second != 0 or dt.microsecond != 0):
        raise Exception("Time part of datetime not 0")
    return date(dt.year, dt.month, dt.day)

reebills_found = 0
reebills_ignored = 0
reebills_with_errors = 0
#Dict {utilbill_id: [{reebill_str (%(account)s-%(sequence)s-%(version)s:[List of errors]},
#                    [List of reebills this utilbill is an editable version of ], utilbill_service, has_error, account]}
utilbill_ids = {}

print "+----------+"
print "| Reebills |"
print "+----------+"
print
stdout.flush()
print >> stderr, "Reebill Errors:"
print >> stderr, "---------------"
print >> stderr
#Find all mongo reebills
for reebill in mongodb.reebills.find().sort([('_id.account',pymongo.ASCENDING),('_id.sequence',pymongo.ASCENDING),('_id.version',pymongo.ASCENDING)]):
    reebills_found += 1
    reebill_error = False
    #Find corresponding reebill in mysql
    reebillresult = session.query(reebill_table).filter(Reebill.customer_id==Customer.id).filter(Customer.account==reebill['_id']['account']).filter(Reebill.sequence==reebill['_id']['sequence']).all()
    reebill_string = "%s-%s-%s"%(reebill['_id']['account'],reebill['_id']['sequence'],reebill['_id']['version'])
    #should be a one-to-one correspondance
    if len(reebillresult)==0:
        #sequence 0s should have no mysql entry
        if reebill['_id']['sequence'] == 0:
            #check that utilbills refered to by sequence 0s exist
            utilbills = reebill['utilbills']
            for i in range(len(utilbills)):
                utilbillresults = mongodb.utilbills.find({'_id':utilbills[i]['id']})
                #it should only point to one
                if utilbillresults.count() == 0:
                    reebill_error = True
                    print >> stderr, "No utility bill for reebill "+reebill_string

                elif utilbillresults.count() > 1:
                    reebill_error = True
                    print >> stderr, "More than one utility bill for reebill "+reebill_string
                utilbillresults = [_ub for _ub in utilbillresults]
                #Add the utility bills to the list of found utility bills
                for _ub in utilbillresults:
                    ub_id = _ub['_id']
                    if utilbill_ids.has_key(ub_id):
                        utilbill_ids[ub_id][0][reebill_string] = []
                    else:
                        utilbill_ids[ub_id] = [{reebill_string:[]},[],_ub['service'],False,_ub['account']]
                #Check that the account, sequence and version match
                if not reebill_error:
                    ub = utilbillresults[0]
                    if not ub.has_key('account'):
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Missing account")
                    elif ub['account'] != reebill['_id']['account']:
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Wrong account: %s"%(ub['account']))
                    if not ub.has_key('sequence'):
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Missing sequence")
                    elif ub['sequence'] != reebill['_id']['sequence']:
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Wrong sequence: %s"%(ub['sequence']))
                    if not ub.has_key('version'):
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Missing version")
                    elif ub['version'] != reebill['_id']['version']:
                        utilbill_ids[ub_id][3] = True
                        utilbill_ids[ub_id][0][reebill_string].append("Wrong version: %s"%(ub['version']))
            if reebill_error:
                reebills_with_error += 1
            else:
                reebills_ignored += 1
                if print_ignores:
                    print >> stderr, "Ignoring reebill %s-%s-%s"%(reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'])
                    print >> stderr
        #Anything not sequence 0 should exist in mysql
        else:
            reebills_with_errors += 1
            print >> stderr, "Missing mysql entry for reebill %s-%s-%s"%(reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'])
            print >> stderr
        continue
    if len(reebillresult)>1:
        reebills_with_errors += 1
        print >> stderr, "Found more than one reebill for %s-%s"%(reebill['_id']['account'], reebill['_id']['sequence'])
        print >> stderr
        continue

    #Find all utility bills attached to this reebill in mysql
    ubs_table = session.query(Utilbill.service, Utilbill.period_start, Utilbill.period_end, Utilbill.rebill_id, Customer.account).filter(Customer.id==Utilbill.customer_id).filter(Customer.account==reebill['_id']['account']).subquery('ubs')
    ubs = ubs_table.c
    sql_info = session.query(ubs.account, Reebill.sequence, Reebill.max_version, Reebill.issued, ubs.service, ubs.period_start, ubs.period_end).filter(Reebill.id==ubs.rebill_id).filter(Reebill.sequence==reebill['_id']['sequence'])

    sql_utilbills = sql_info.all()

    #Find all utility bills pointed to by this reebill
    utilbills = reebill['utilbills']
    if len(utilbills) != len(sql_utilbills):
        reebill_error = True
        print >> stderr, "Wrong number of utility bills for reebill:",reebill['_id']
        print >> stderr, "    Got:",len(utilbills)
        print >> stderr, "    Expected:",len(sql_utilbills)

    for i in range(len(utilbills)):
        #Find the utility bill pointed to by the reebill
        utilbillresults = mongodb.utilbills.find({'_id':utilbills[i]['id']})
        #There should only be one
        if utilbillresults.count() == 0:
            reebill_error = True
            print >> stderr, "No utility bill for reebill %s-%s-%s"%(reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'])
            print >> stderr, "    utilbill._id:",utilbills[i]['id']
            print >> stderr
            continue
        elif utilbillresults.count() > 1:
            reebill_error = True
            print >> stderr, "More than one utility bill for reebill %s-%s-%s"%(reebill['_id']['account'], reebill['_id']['sequence'], reebill['_id']['version'])
            print >> stderr, "    utilbill._id:",utilbills[i]['id']
            print >> stderr
            continue
        utilbillresults = [_ub for _ub in utilbillresults]
        #Add them (it) to found utilbills
        for _ub in utilbillresults:
            ub_id = _ub['_id']
            if utilbill_ids.has_key(ub_id):
                utilbill_ids[ub_id][0][reebill_string] = []
            else:
                utilbill_ids[ub_id] = [{reebill_string:[]},[],_ub['service'],False,_ub['account']]
        ub = utilbillresults[0]
        service = ub['service']
        #Match this utility bill to one in mysql
        sql_ubs = [x for x in sql_utilbills if x.service==service]

        has_error = False
        might_find_editable = True
        #As of release 13, all reebills should have attached utility bills
        if len(sql_ubs) == 0:
            utilbill_ids[ub_id][3] = True
            utilbill_ids[ub_id][0][reebill_string].append("Could not find match in mysql")
            utilbill_ids[ub_id][0][reebill_string].append("    Available: %s"%sql_utilbills)
        elif len(sql_ubs) > 1:
            utilbill_ids[ub_id][3] = True
            utilbill_ids[ub_id][0][reebill_string].append("Found more than one match in mysql")
            utilbill_ids[ub_id][0][reebill_string].append("    Available: %s"%sql_utilbills)
        else:
            #Check that all the fields agree with mysql
            sql_ub = sql_ubs[0]
            if not ub.has_key('account'):
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Missing account")
                might_find_editable = False
            elif ub['account'] != sql_ub.account:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Wrong account: %s"%ub['account'])
            if not ub.has_key('start'):
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Missing start date")
                might_find_editable = False
            elif datetime_to_date(ub['start']) != sql_ub.period_start:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Wrong start date:")
                utilbill_ids[ub_id][0][reebill_string].append("    Got: %s"%datetime_to_date(ub['start']))
                utilbill_ids[ub_id][0][reebill_string].append("    Expected: %s"%sql_ub.period_start)
            if not ub.has_key('end'):
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Missing end date")
                might_find_editable = False
            elif datetime_to_date(ub['end']) != sql_ub.period_end:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Wrong end date:")
                utilbill_ids[ub_id][0][reebill_string].append("    Got: %s"%datetime_to_date(ub['end']))
                utilbill_ids[ub_id][0][reebill_string].append("    Expected: %s"%sql_ub.period_end)
            if not ub.has_key('sequence'):
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Missing sequence")
            elif ub['sequence'] != reebill['_id']['sequence']:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Wrong sequence: %s"%(ub['sequence']))
            if not ub.has_key('version'):
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Missing version")
            elif ub['version'] != reebill['_id']['version']:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("Wrong version: %s"%(ub['version']))

        #Find editable utility bills corresponding to this utility bill
        #Defined by having all the same fields except sequence and version not existing
        editable_ubs = []
        if might_find_editable:
            editable_utilbillresults = mongodb.utilbills.find({'account':ub['account'], 'start':ub['start'], 'end':ub['end'], 'service':ub['service'], 'sequence':{'$exists':False}, 'version':{'$exists':False}})
            #Utilbill can't be the editable version of itself
            editable_ubs = [eub for eub in editable_utilbillresults if eub['_id'] != ub['_id']]

            for _eub in editable_ubs:
                eub_id = _eub['_id']
                if utilbill_ids.has_key(eub_id):
                    utilbill_ids[eub_id][1].append(reebill_string)
                else:
                    utilbill_ids[eub_id] = [{},[reebill_string],_eub['service'],False,_eub['account']]

            if len(editable_ubs) == 0:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("No editable utility bills found")
            elif len(editable_ubs) > 1:
                utilbill_ids[ub_id][3] = True
                utilbill_ids[ub_id][0][reebill_string].append("More than one editable utility bill found:")
                for _eub in editable_ubs:
                    utilbill_ids[ub_id][0][reebill_string].append("    %s"%_eub['_id'])

        if reebill_error:
            reebills_with_errors += 1
            print >> stderr

stderr.flush()
print "Found:",reebills_found
print "Ignored:",reebills_ignored
print "With no errors:",reebills_found-reebills_with_errors-reebills_ignored
print "With errors:",reebills_with_errors
print
print "+-----------+"
print "| Utilbills |"
print "+-----------+"
print
stdout.flush()
print >> stderr, "Utilbill Errors:"
print >> stderr, "----------------"
print >> stderr
utilbills_with_errors = 0
utilbills_not_used = 0
#Figure out what utilbills weren't found
for utilbill in mongodb.utilbills.find():
    if not utilbill_ids.has_key(utilbill['_id']):
        utilbills_not_used += 1
        utilbill_ids[utilbill['_id']]=[{},[],utilbill['service'],False,utilbill['account']]
        print >> stderr, "Utilbill never used:",utilbill['_id']
if utilbills_not_used:
    print >> stderr

utilbills_used_more_than_once = 0

#Sort utilbills by account
sorted_ub_ids = OrderedDict(sorted(utilbill_ids.items(), key=lambda t: t[1][4]))
for ub_id, rb_list in sorted_ub_ids.iteritems():
    has_error = False
    #If pointed to by more than one reebill
    if len(rb_list[0].keys()) + len(rb_list[1]) > 1:
        all_same_sequence = False
        #Different versions of the same bill should have the same editable version
        if (len(rb_list[0].keys())==0):
            first = rb_list[1][0]
            first = first[:first.rfind('-')]
            all_same_sequence = True
            for rb_str in rb_list[1]:
                if rb_str[:rb_str.rfind('-')] != first:
                    all_same_sequence = False
        if not all_same_sequence:
            #Don't double count utilbill errors
            rb_list[3] = False
            has_error = True
            utilbills_used_more_than_once += 1
            print >> stderr, "Utilbill %s (%s) used by reebills:"%(ub_id,rb_list[2])
            for rb_str in rb_list[0].keys():
                print >> stderr, "    "+rb_str
            for rb_str in rb_list[1]:
                print >> stderr, "   E"+rb_str
    if rb_list[3]:
        utilbills_with_errors += 1
        has_error = True
        print >> stderr, "Utilbill %s (%s) has errors:"%(ub_id,rb_list[2])
    #Print errors for each reebill pointing to this bill
    for rb_str, error_list in rb_list[0].items():
        if len(error_list) > 0:
            print >> stderr, "For reebill "+rb_str+":"
            for error in error_list:
                print >> stderr, "    "+error
    if has_error:
        print >> stderr

stderr.flush()
print "Found:",len(utilbill_ids.keys())
print "With no errors:",len(utilbill_ids.keys())-utilbills_with_errors-utilbills_not_used-utilbills_used_more_than_once
print "Not found:",utilbills_not_used
print "Found >1 time:",utilbills_used_more_than_once
print "With other errors:",utilbills_with_errors
print
stdout.flush()
