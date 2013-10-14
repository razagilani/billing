'''
This script updates existing data to match the new design in which any utility
bill document attached to a reebill is frozen (i.e. contains the keys
"sequence" and "version") if and only if the reebill is issued. In the old
design, unissued reebills with sequence 0 are attached to frozen utility bill
documents, but in the new design they should be attached to editable utility
bill documents.

This is accomplished by converting frozen utility bill documents into editable
ones. Any existing editable version of the same utility bill is replaced,
because it is probably less less up-to-date than the frozen one. (It is not
always possible to find an "editable version" of a particular frozen utility
bill, because they are not linked by a primary key.)

Also, this script deletes editable utility bill documents that have a frozen
version attached to an issued reebill (i.e. all editable utility bill
documents) and recreates them by copying the newest frozen version. This is not
schema change; it just ensures that editable utility bill documents are
up-to-date, because most of them are not.

After the script has run, all utility bill documents that a reebill document
is attached to should be "frozen" if the reebill is issued and "editable" if it
is not, and all the editable utility bills that have a frozen version should be
identical to the latest frozen version.
'''
from sys import stderr
import pymongo
from bson import ObjectId
import MySQLdb
from billing.util.dateutils import date_to_datetime
from billing.util.dictutils import subdict, dict_merge
from billing.util.mongo_utils import format_query, check_error
from billing.processing.exceptions import MongoError

def unfreeze_utilbill(utilbill_doc, new_id=None):
    '''Converts 'utilbill_doc' into an editable utility bill document, i.e.
    removes its "sequence" and "version" keys, and saves it.
    
    If 'new_id' is given, a new document is created with that _id the frozen
    one is unchanged. If 'new_id' is not given, the original document is
    modified and saved with its original _id, so the frozen document has become
    editable. In both cases, any existing editable document having the same
    service, utility, and dates is removed.

    Returns a list of _ids of documents that were removed.
    '''
    # find any existing editable utility bill documents with the same utility,
    # service, and dates
    query_for_editable_twins = dict_merge(
            subdict(utilbill_doc, ['account', 'utility', 'service', 'start',
            'end']), {'sequence': {'$exists': False}})
    editable_twins = list(db.utilbills.find(query_for_editable_twins))

    # there should be at most 1 editable version of this utility bill
    if len(editable_twins) == 0:
        print >> stderr, ('WARNING expected an editable version of this '
                'utility bill document to exist before being replaced: %s') % \
                format_query(query_for_editable_twins)
    if len(editable_twins) > 1:
        print >> stderr, ('WARNING %s editable utility bills match this '
                'query: %s; both will be deleted') % (len(editable_twins),
                format_query(query_for_editable_twins))

    # remove existing editable version(s), if there were any
    for twin in editable_twins:
        check_error(db.utilbills.remove({'_id': twin['_id']}, True))

    # "un-freeze" the utility bill to which the reebill is attached
    # ('pop' won't complain if the keys are missing)
    utilbill_doc.pop('sequence', None)
    utilbill_doc.pop('version', None)

    if new_id:
        # change the _id so this document will not replace an existing one when
        # inserted
        utilbill_doc['_id'] = new_id
        db.utilbills.insert(utilbill_doc, continue_on_error=False)
    else:
        # convert the previously frozen document into an editable one, and save
        # it without changing its id
        db.utilbills.save(utilbill_doc, safe=True)
    assert db.error() is None

    return [twin['_id'] for twin in editable_twins]


db = pymongo.Connection('localhost')['skyline-dev']
con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
con.autocommit(False)
cur = con.cursor()

# part 1:
# un-freeze frozen utility bill documents attached to unissued version-0
# reebills, replacing editable versions of the same utility bills.
query_for_unissued_version_0_reebills = '''
select distinct customer.account, sequence, utilbill_id
from reebill join customer join utilbill_reebill
on customer_id = customer.id and reebill_id = reebill.id
where version = 0 and issued != 1
order by account, sequence'''

cur.execute(query_for_unissued_version_0_reebills)
for account, sequence, utilbill_id in cur.fetchall():
    reebill_doc = db.reebills.find_one({'_id.account': account, '_id.sequence':
            sequence, '_id.version': 0})
    assert reebill_doc is not None

    for utilbill_subdoc in reebill_doc['utilbills']:

        # find utility bill document attached to the reebill
        utilbill = db.utilbills.find_one({'_id': utilbill_subdoc['id']})
        if utilbill is None:
            print >> stderr, ('No utility bill document for unissued reebill '
                    '%s-%s-%s, id %s') % (reebill_doc['_id']['account'],
                    reebill_doc['_id']['sequence'],
                    reebill_doc['_id']['version'], utilbill_subdoc['id'])
            continue

        # make sure this document really is "frozen", i.e. has "sequence" and
        # "version" keys in it
        try:
            assert 'sequence' in utilbill and 'version' in utilbill
        except AssertionError:
            print >> stderr, ('WARNING unissued version-0 reebill lacks '
                    '"sequence" and "version" keys in utility bill document: %s'
                    % reebill_doc['_id'])
            # when the document is already "unfrozen", there is nothing to do
            continue

        # replace the existing editable utility bill with the previously frozen
        # one, now editable
        unfreeze_utilbill(utilbill)

        # NOTE that a new document is not being created, so the document can
        # keep the same _id and the reebill subdocument "id" field does not
        # need to be updated. (And the utilbill.document_id in MySQL does not
        # exist yet; when it is created in 06_utilbill_id_utility_rs it should
        # be set to this _id.)


# part 2:
# replace editable version of every utility bill document with a copy of the
# frozen document attached to the highest-version issued reebill.
query_for_highest_version_issued_reebills = '''
select account, sequence, max(version)
from reebill join customer on customer.id = customer_id
where issued = 1
group by customer_id, sequence
order by customer_id, sequence, version'''
cur.execute(query_for_highest_version_issued_reebills)
for account, sequence, max_version in cur.fetchall():
    reebill_doc = db.reebills.find_one({'_id.account': account, '_id.sequence':
            sequence, '_id.version': max_version})
    assert reebill_doc is not None

    for utilbill_subdoc in reebill_doc['utilbills']:
        utilbill_doc_id = utilbill_subdoc['id']
        utilbill_doc = db.utilbills.find_one({'_id': utilbill_doc_id})
        if utilbill_doc is None:
            print >> stderr, ('No utility bill document for reebill %s-%s-%s, '
                    'id %s') % (account, sequence, max_version,
                    utilbill_doc_id)
            continue

        # make sure this document really is "frozen", i.e. has "sequence" and
        # "version" keys in it
        try:
            assert 'sequence' in utilbill_doc and 'version' in utilbill_doc
        except AssertionError:
            print >> stderr, ('issued reebill lacks "sequence" and "version"'
                    ' in its utility bill: %s') % reebill_doc['_id']

        new_id = ObjectId()
        removed_ids = unfreeze_utilbill(utilbill_doc, new_id=new_id)

        # even though this is an issued bill, there may be an unissued reebill
        # (with version > 0) referring to the editable utility bill document.
        # the "id" in this reebill's document needs to be updated to match the
        # "_id" of the new editable utility bill document.
        for _id in removed_ids:
            reebill_docs = list(db.reebills.find({'utilbills.id': _id}))
            if len(reebill_docs) == 0:
                print 'replaced editable utility bill document with no reebills', _id
                continue
            # any reebill document referring to this utility bill should be an
            # unissued correction with 1 utility bill
            for result in db.reebills.find({'utilbills.id': _id}):
                assert len(result['utilbills']) == 1
                assert result['_id']['version'] > 0
                assert result['issue_date'] is None
                print '######### updating utilbill id of unissued correction %s-%s-%s, _id %s' % (account, result['_id']['sequence'], result['_id']['version'], _id)
            # NOTE this sets all utilbill "id" fields to the same value, but
            # there should always be 1
            check_error(db.reebills.update({'utilbills.id': _id}, {'$set': {'utilbills.$.id': new_id}}, safe=True))
            print db.reebills.find({'utilbills.id': new_id}).count()

con.commit()


