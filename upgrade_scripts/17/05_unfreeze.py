'''
Converts frozen utility bill documents attached to unissued version-0 reebills into editable ones, replacing any editable utility bills that already exist.
Deletes editable utility bill documents that have a frozen version attached to an issued reebill, and recreates them by copying the newest frozen version.
'''
from sys import stderr
import pymongo
from billing.util.dateutils import date_to_datetime
from bson import ObjectId
import MySQLdb
from billing.util.dictutils import subdict, dict_merge

db = pymongo.Connection('localhost')['skyline-dev']
con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)

def unfreeze_utilbill(utilbill_doc, new_id=None):
    '''Converts 'utilbill_doc' into an "editable" utility bill document, i.e.
    without "sequence" and "version" keys, and saves it. If 'new_id' is given,
    a new document is created with that _id the frozen one is unchanged. If
    'new_id' is not given, the original document is modified and saved with its
    original _id, so the frozen document has become editable. In both cases,
    any existing editable document having the same service, utility, and dates
    is removed.'''
    # make sure this document really is "frozen", i.e. has "sequence" and "version" keys in it
    assert 'sequence' in utilbill_doc
    assert 'version' in utilbill_doc

    # find any existing editable utility bill documents with the same utility, service, and dates
    query_for_editable_twins = dict_merge(
            subdict(utilbill_doc, ['account', 'utility', 'service', 'start', 'end']),
            {'sequence': {'$exists': False}})
    editable_twins = db.utilbills.find(query_for_editable_twins)

    # there should be at most 1 editable version of this utility bill
    if editable_twins.count() == 0:
        return
    if editable_twins.count() > 1:
        print >> stderr, editable_twins.count(), 'editable utility bills match this query:', query_for_editable_twins
        return

    # "un-freeze" the utility bill to which the reebill is attached
    del utilbill_doc['sequence']
    del utilbill_doc['version']

    if new_id:
        # change the _id so this document will not replace an existing one when sav
        utilbill_doc['_id'] = new_id
    else:
        # convert the previously frozen document into an editable one, without changing its id
        pass

    db.utilbills.save(utilbill_doc)
    db.utilbills.remove({'_id': editable_twins[0]['_id']}, True)





# TODO should this be done?
## remove all editable utility bill documents so that better ones can be
## recreated from the frozen ones
#db.utilbills.remove({'sequence': {'$exists': False}})

# unissued version-0 reebills are currently attached to utility bills that have
# "sequence" and "version" keys in them (which can still be edited by the user)
# but should be attached to editable ones (without "sequence" and "version").
# convert these frozen utility bills into editable ones, replacing editable
# ones that are already there.
cur = con.cursor()
cur.execute('''select distinct customer.account, sequence, utilbill_id
from reebill join customer join utilbill_reebill on customer_id = customer.id and reebill_id = reebill.id
where version = 0 and issued != 1
order by account, sequence''')

for account, sequence, utilbill_id in cur.fetchall():
    reebill_doc = db.reebills.find_one({'_id.account': account, '_id.sequence': sequence, '_id.version': 0})

    for utilbill_subdoc in reebill_doc['utilbills']:

        # find utility bill document attached to the reebill
        utilbill = db.utilbills.find_one({'_id': utilbill_subdoc['id']})
        if utilbill is None:
            print >> stderr, 'No utility bill document for reebill %s-%s-%s, id %s' % (reebill_doc['_id']['account'], reebill_doc['_id']['sequence'], reebill_doc['_id']['version'], utilbill_subdoc['id'])
            continue

        # replace the existing editable utility bill with the previously frozen one, now editable
        # NOTE that a new document is not being created, so the document can
        # keep the same _id and the reebill subdocument "id" field does not
        # need to be updated
        try:
            unfreeze_utilbill(utilbill)
        except AssertionError:
            print >> stderr, 'unissued version-0 reebill lacks "sequence" and "version" in its utility bill:', reebill_doc['_id']


# all issued reebills have an editable version of the frozen utility bill
# document they are attached to. this document is unlikely to be accurate
# because the user has not been able to edit it. so replace it with an new one
# made by copying the frozen document attached to the highest-version reebill.
cur.execute('''select account, sequence, max(version)
from reebill join customer on customer.id = customer_id
where issued = 1
group by customer_id, sequence
order by customer_id, sequence, version''')
for account, sequence, max_version in cur.fetchall():
    reebill_doc = db.reebills.find_one({'_id.account': account, '_id.sequence': sequence, '_id.version': max_version})
    for utilbill_subdoc in reebill_doc['utilbills']:
        utilbill_doc_id = utilbill_subdoc['id']
        utilbill_doc = db.utilbills.find_one({'_id': utilbill_doc_id})

        try:
            unfreeze_utilbill(utilbill_doc, new_id=ObjectId())
        except AssertionError:
            print >> stderr, 'issued reebill lacks "sequence" and "version" in its utility bill:', reebill_doc['_id']
con.commit()


