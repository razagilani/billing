from datetime import date, datetime
import copy
from itertools import chain

import bson # part of pymongo package
from sqlalchemy.orm.exc import NoResultFound

from billing.util.mongo_utils import bson_convert, format_query, check_error
from billing.util.dateutils import date_to_datetime
from billing.processing.state import Customer, UtilBill
from billing.exc import NoSuchBillException, \
    NotUniqueException, IssuedBillError, MongoError


def convert_datetimes(x, datetime_keys=[], ancestor_key=None):
    # TODO combine this into python_convert(), and include the ancestor_key
    # argument, and datetime_keys (or maybe a dictionary mapping key names to
    # types in general, so any type conversion could be done according to key
    # name)
    '''If x is a datetime, returns the date part of x unless ancestor_key is in
    in datetime_keys. If x is a dictionary, convert_datetimes() is recursively
    applied to all values in dictionary, with ancestor_key set to the key of
    each value. If x is a list, convert_datetimes() is recursively applied to
    all values with ancestor_key unchanged (so each item in the list or any
    descendant list is converted according to the key of its closest ancestor
    that was a dictionary). In the root call of this function, x should be a
    dictionary and the ancestor_key argument should be omitted; an ancestor_key
    must be given if x is anything other than a dictionary.'''
    if type(x) is not dict and ancestor_key is None:
        raise ValueError(("Can't convert %s into a date or datetime without"
            "an ancestor key.") % x)
    if type(x) is datetime:
        return x if ancestor_key in datetime_keys else x.date()
    if type(x) is dict:
        return dict((key, convert_datetimes(value, datetime_keys, key))
            for key, value in x.iteritems())
    if type(x) is list:
        return [convert_datetimes(element, datetime_keys, ancestor_key) for
                element in x]
    return x

# TODO make this a method of a utility bill document class when one exists
def get_all_actual_registers_json(utilbill_doc):
    '''Given a utility bill document, returns a list of dictionaries describing
    registers of all meters. (The "actual" in the name has nothing
    to do with "actual charges".)'''
    result = []
    for meter in utilbill_doc['meters']:
        for register in meter['registers']:
            # compensate for unpredictable database schema by inserting ''
            # for missing keys
            result.append({
                'meter_id': meter['identifier'],
                'register_id': register['identifier'],
                'service': utilbill_doc['service'],
                'type': register.get('type', ''),
                'binding': register.get('register_binding', ''),
                'description': register.get('description', ''),
                'quantity': register.get('quantity', 0),
                'quantity_units': register.get('quantity_units', ''),

                # insert an "id" key that uniquely identifies these
                # objects. this is used by client code; TODO consider
                # moving into wsgi.py or somewhere else, but currently
                # inserting the "id" here is the simplest and avoids
                # repetition
                'id' : '%s/%s/%s' % (utilbill_doc['service'],
                        meter['identifier'], register['identifier'])
            })
    return result


# TODO make this a method of a utility bill document class when one exists
def new_register(utilbill_doc, meter_identifier=None, identifier = None):
    if meter_identifier is None:
        meter_identifier = _new_meter(utilbill_doc)['identifier']
    meter = _meter(utilbill_doc, meter_identifier)
    if meter is None:
        meter = _new_meter(utilbill_doc, meter_identifier)
    if identifier is None:
        identifier = 'Insert register ID here'
    new_actual_register = {
        "description" : "Insert description",
        "quantity" : 0,
        "quantity_units" : "therms",
        "identifier" : identifier,
        "type" : "total",
        "register_binding": "Insert register binding here"
    }
    for reg in meter['registers']:
        if reg['identifier'] == identifier:
            raise ValueError('Register %s for meter %s already exists.' %
                    (identifier, meter_identifier))
    meter['registers'].append(new_actual_register)

    return (meter_identifier, new_actual_register)

# TODO make this a method of a utility bill document class when one exists
def _meter(utilbill_doc, identifier):
    '''Returns the first meter found with the given identifier in the given
    utility bill document. Raises StopIteration if none was found.'''
    meter = next(meter for meter in utilbill_doc['meters'] if
            meter['identifier'] == identifier)
    return meter

# TODO make this a method of a utility bill document class when one exists
def _delete_meter(utilbill_doc, identifier):
        utilbill_doc['meters'][:] = [meter for meter in utilbill_doc['meters']
                if meter['identifier'] != identifier]

# TODO make this a method of a utility bill document class when one exists
def _new_meter(utilbill_doc, identifier=None):
    if any(m['identifier'] == identifier for m in utilbill_doc['meters']):
        raise ValueError('Meter %s for already exists' % (identifier))
    if identifier is None:
        identifier = 'Insert meter ID here'
    new_meter = {
        'identifier': identifier,
        'present_read_date': utilbill_doc['end'],
        'prior_read_date': utilbill_doc['start'],
        'registers': [],
    }
    utilbill_doc['meters'].append(new_meter)
    return new_meter

# TODO make this a method of a utility bill document class when one exists
def delete_register(utilbill_doc, meter_identifier, identifier):
    for meter in utilbill_doc['meters']:
        if meter['identifier'] == meter_identifier:
            meter['registers'][:] = [reg for reg in meter['registers'] if reg['identifier'] != identifier]
            if len(meter['registers']) == 0:
                _delete_meter(utilbill_doc, meter_identifier)
                break

# TODO make this a method of a utility bill document class when one exists
def update_register(utilbill_doc, original_meter_id, original_register_id,
        meter_id=None, register_id=None, description=None, quantity=None,
        quantity_units=None, type=None, binding=None):
    '''In the given utility bill document, updates fields in
    the register given by 'original_register_id' in the meter given by
    'original_meter_id'.'''
    # find the meter, and the register within the meter
    meter = _meter(utilbill_doc, original_meter_id)
    register = next(r for r in meter['registers'] if r['identifier'] ==
            original_register_id)
    if register_id is not None:
        existing_registers = [r for r in meter['registers'] if r['identifier']
                              == register_id]
        if len(existing_registers) > 0:
            raise ValueError("There is already a register with id %s and meter"
                             " id %s" %(register_id, original_meter_id))
    if meter_id is not None:
        # meter id is being updated, and there is an existing meter with
        # the given id, the register must be removed from its old meter and
        # inserted into that meter. if there is no meter with that id, the
        # id of the meter containing the register can be changed.
        try:
            existing_meter_with_new_id = _meter(utilbill_doc, meter_id)
        except StopIteration:
            # if there are any other registers in the same meter, a new
            # meter must be created. if not, the meter id can just be
            # changed.
            if len(meter['registers']) > 1:
                # create new meter
                new_meter = _new_meter(utilbill_doc, identifier=meter_id)
                # insert register in new meter
                new_register(utilbill_doc, meter_identifier=meter_id,
                        identifier=original_register_id)
                # remove register from old meter
                delete_register(utilbill_doc, original_meter_id,
                        original_register_id)
                meter = new_meter
            else:
                meter['identifier'] = meter_id
        else:
            existing_registers = [r for r in existing_meter_with_new_id
                                  ['registers'] if r['identifier']
                                  == register_id]
            if len(existing_registers) > 0:
                raise ValueError("There is already a register with id %s and"
                                 " meter id %s"
                                 %(original_register_id, meter_id))
                
            # insert register in new meter
            new_register(utilbill_doc, meter_identifier=
                    existing_meter_with_new_id['identifier'],
                    identifier=original_register_id)
            # remove register from old meter
            delete_register(utilbill_doc, original_meter_id,
                    original_register_id)
            meter = existing_meter_with_new_id
    if description is not None:
        register['description'] = description
    if quantity is not None:
        assert isinstance(quantity, (float, int))
        register['quantity'] = quantity
    if description is not None:
        register['description'] = description
    if quantity_units is not None:
        register['quantity_units'] = quantity_units
    if register_id is not None:
        register['identifier'] = register_id
    if type is not None:
        register['type'] = type
    if binding is not None:
        register['register_binding'] = binding

    return meter['identifier'], register['identifier']


# TODO rename to get_meter_read_period
# TODO make this a method of a utility bill document class when one exists
def meter_read_period(utilbill_doc):
    '''Returns the period dates of the first (i.e. only) meter in this bill.
    '''
    assert len(utilbill_doc['meters']) >= 1
    meter = utilbill_doc['meters'][0]
    return meter['prior_read_date'], meter['present_read_date']

class MongoReebill(object):
    @classmethod
    def get_reebill_doc_for_utilbills(cls, account, sequence, version,
                discount_rate, late_charge_rate, utilbill_docs):
        '''Returns a newly-created MongoReebill object having the given account
        number, discount rate, late charge rate, and list of utility bill
        documents. Hypothetical charges are the same as the utility bill's
        actual charges.
        Note that the utility bill document _id is not changed; the caller is
        responsible for properly duplicating utility bill documents.
        '''
        assert len(utilbill_docs) == 1
        reebill_doc = {
            "_id" : {
                "account" : account,
                "sequence" : sequence,
                "version" : version,
            },
        }
        return MongoReebill(reebill_doc, utilbill_docs)

    def __init__(self, reebill_data, utilbill_dicts):
        assert isinstance(reebill_data, dict)
        # defensively copy whatever is passed in; who knows where the caller got it from
        self.reebill_dict = copy.deepcopy(reebill_data)

    @property
    def account(self):
        return self.reebill_dict['_id']['account']
    @account.setter
    def account(self, value):
        self.reebill_dict['_id']['account'] = value
    
    @property
    def sequence(self):
        return self.reebill_dict['_id']['sequence']
    @sequence.setter
    def sequence(self, value):
        self.reebill_dict['_id']['sequence'] = value

    @property
    def version(self):
        return self.reebill_dict['_id']['version']
    @version.setter
    def version(self, value):
        self.reebill_dict['_id']['version'] = int(value)
    
class ReebillDAO(object):
    '''A "data access object" for reading and writing reebills in MongoDB.'''

    def __init__(self, state_db, database, **kwargs):
        self.state_db = state_db
        self.reebills_collection = database['reebills']
        self.utilbills_collection = database['utilbills']

    def load_utilbill(self, account, service, utility, start, end,
            sequence=None, version=None):
        '''Loads exactly one utility bill document from Mongo, returns the raw
        dictionary. Raises a NoSuchBillException if zero or multiple utility
        bills are found.
        
        'start' and 'end' may be None because there are some reebills that have
        None dates (when the dates have not yet been filled in by the user).
        
        'sequence' and 'version' are optional because they only apply to a
        frozen utility bill that belongs to a particular issued reebill
        version. A specific sequence or version may be given, or a boolean to
        test for the existence of the 'sequence' or 'version' key.'''

        query = {
            'account': account,
            'utility': utility,
            'service': service,
            'start': date_to_datetime(start) \
                    if isinstance(start, date) else None,
            'end': date_to_datetime(end) \
                    if isinstance(end, date) else None,
        }

        # "sequence" and "version" may be int for specific sequence/version, or
        # boolean to query for key existence
        # NOTE bool must be checked first because bool is a subclass of
        # int! http://www.python.org/dev/peps/pep-0285/
        if isinstance(sequence, bool):
            query['sequence'] = {'$exists': sequence}
        elif isinstance(sequence, int):
            query['sequence'] = sequence
        elif sequence is not None:
            raise ValueError("'sequence'=%s; must be int or boolean" % sequence)

        if isinstance(version, bool):
            query['version'] = {'$exists': version}
        elif isinstance(version, int):
            query['version'] = version
        elif version is not None:
            raise ValueError("'version'=%s; must be int or boolean" % version)

        docs = self.utilbills_collection.find(query)

        # make sure exactly one doc was found
        if docs.count() == 0:
            raise NoSuchBillException(("No utility bill found in %s: "
                    "query was %s") % (self.utilbills_collection,
                    format_query(query)))
        elif docs.count() > 1:
            raise NotUniqueException(("Multiple utility bills in %s satisfy "
                    "query %s") % (self.utilbills_collection,
                    format_query(query)))
        return docs[0]

    def _load_utilbill_by_id(self, _id):
        docs = self.utilbills_collection.find({'_id': bson.ObjectId(_id)})
        if docs.count() == 0:
            raise NoSuchBillException("No utility bill document for _id %s"
                    % _id)
        assert docs.count() == 1
        result = docs[0]
        result = convert_datetimes(result)
        return result

    def load_doc_for_utilbill(self, utilbill, reebill=None):
        '''Returns the Mongo utility bill document corresponding to the given
        state.UtilBill object.

        If 'reebill' is None, this is the "current" document, i.e. the one
        whose _id is in the utilbill table.

        If a ReeBill is given, this is the document for the version of the
        utility bill associated with the current reebill--either the same as
        the "current" one if the reebill is unissued, or a frozen one (whose
        _id is in the utilbill_reebill table) if the reebill is issued.'''
        if utilbill.state == UtilBill.Hypothetical:
            assert utilbill.document_id == None
            assert utilbill.uprs_document_id == None
            raise ValueError('No document for hypothetical utilty bill: %s'
                    % utilbill)
        # empty document_ids are legitimate because "hypothetical" utility
        # bills do not have a document
        # empty document_ids should not be possible, once the db is cleaned up
        # (there's already a "not null" constraint for 'document_id' but the
        # default value is "")
        if reebill is None or reebill.document_id_for_utilbill(utilbill) \
                is None:
            return self._load_utilbill_by_id(utilbill.document_id)
        return self._load_utilbill_by_id(
                reebill.document_id_for_utilbill(utilbill))

    def delete_doc_for_statedb_utilbill(self, utilbill_row):
        '''Deletes the Mongo utility bill document corresponding to the given
        state.UtilBill object.'''
        if utilbill_row._utilbill_reebills != []:
            raise ValueError(("Can't delete a utility bill that has "
                    "reebills associated with it"))
        result = self.utilbills_collection.remove({
                '_id': bson.ObjectId(utilbill_row.document_id)}, safe=True)
        if result['err'] is not None or result['n'] == 0:
            raise MongoError(result)

    def load_utilbill_template(self, session, account):
        '''Returns the Mongo utility bill document template for the customer
        given by 'account'.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        assert customer.utilbill_template_id not in (None, '')
        docs = self.utilbills_collection.find({
                '_id': bson.ObjectId(customer.utilbill_template_id)})
        if docs.count() == 0:
            raise NoSuchBillException("No utility bill template for %s" %
                    customer)
        assert docs.count() == 1
        utilbill_doc = docs[0]

        # convert types
        utilbill_doc = convert_datetimes(utilbill_doc)

        return utilbill_doc

    def _load_all_utillbills_for_reebill(self, reebill_doc):
        '''Loads all utility bill documents from Mongo that match the ones in
        the 'utilbills' list in the given reebill dictionary (NOT MongoReebill
        object). Returns list of dictionaries with converted types.'''
        result = []

        for utilbill_handle in reebill_doc['utilbills']:
            query = {'_id': utilbill_handle['id']}
            utilbill_doc = self.utilbills_collection.find_one(query)
            if utilbill_doc == None:
                raise NoSuchBillException(("No utility bill found for reebill "
                        " %s-%s-%s in %s: query was %s") % (
                        reebill_doc['_id']['account'],
                        reebill_doc['_id']['sequence'], reebill_doc['_id']['version'],
                        self.utilbills_collection, format_query(query)))
            utilbill_doc = convert_datetimes(utilbill_doc)
            result.append(utilbill_doc)

        return result

    def load_reebill(self, account, sequence, version='max'):
        '''Returns the reebill with the given account and sequence, and the a
        version: a specific version number, an issue date (before which the
        greatest issued version is returned, and after which the greatest
        overall version is returned), or 'max', which specifies the greatest
        version overall.'''
        assert isinstance(account, basestring)
        assert isinstance(sequence, long) or isinstance(sequence, int)
        assert isinstance(version, basestring) or isinstance(version, long) \
                or isinstance(version, int) or isinstance(version, date)

        query = {"_id.account": account, "_id.sequence": sequence}

        # TODO figure out how to move this into _get_version_query(): it can't
        # be expressed as part of the query, except maybe with a javascript
        # "where" clause
        if isinstance(version, int) or isinstance(version, long):
            query.update({'_id.version': version})
            mongo_doc = self.reebills_collection.find_one(query)
        elif version == 'max':
            # get max version from MySQL, since that's the definitive source of
            # information on what officially exists (but version 0 reebill
            # documents are templates that do not go in MySQL)
            try:
                if sequence != 0:
                    max_version = self.state_db.max_version(account, sequence)
                    query.update({'_id.version': max_version})
                mongo_doc = self.reebills_collection.find_one(query)
            except NoResultFound:
                # customer not found in MySQL
                mongo_doc = None
        else:
            raise ValueError('Unknown version specifier "%s" (%s)' %
                    (version, type(version)))

        if mongo_doc is None:
            raise NoSuchBillException(("no reebill found in %s: query was %s")
                    % (self.reebills_collection, format_query(query)))

        # convert types in reebill document
        mongo_doc = convert_datetimes(mongo_doc) # this must be an assignment because it copies

        return MongoReebill(mongo_doc, [])

    def load_reebills_for(self, account, version='max'):
        sequences = self.state_db.listSequences(account)
        return [self.load_reebill(account, sequence, version) for sequence in sequences]
    
    def save_reebill(self, reebill, force=False):
        '''Saves the given reebill document.

        Replacing an already-issued reebill (as determined by StateDB) or its
        utility bills is forbidden unless 'force' is True (this should only be
        used for testing).
        '''
        issued = self.state_db.is_issued(reebill.account, reebill.sequence,
                    version=reebill.version, nonexistent=False)
        if issued and not force:
            raise IssuedBillError("Can't modify an issued reebill.")

        reebill_doc = bson_convert(copy.deepcopy(reebill.reebill_dict))
        self.reebills_collection.save(reebill_doc, safe=True)
        # TODO catch mongo's return value and raise MongoError

    def save_utilbill(self, utilbill_doc, sequence_and_version=None,
            force=False):
        '''Save raw utility bill dictionary. If this utility bill belongs to an
        issued reebill (i.e. has sequence and version in it) it can't be saved.
        force=True overrides this rule; only use it for testing.

        'sequence_and_version' should a (sequence, version) tuple, to be used
        when (and only when) issuing the containing reebill for the first time
        (i.e. calling save_reebill_and_utilbill(freeze_utilbills=True). This puts sequence
        and version keys into the utility bill. (If those keys are already in
        the utility bill, you won't be able to save it.)
        '''
        if 'sequence' in utilbill_doc or 'version' in utilbill_doc:
            assert 'sequence' in utilbill_doc and 'version' in utilbill_doc
            if not force:
                raise IssuedBillError(("Can't save utility bill document "
                    "because it belongs to issued reebill %s-%s-%s") % (
                        utilbill_doc['account'], utilbill_doc['sequence'],
                        utilbill_doc['version']))

        if sequence_and_version is not None:
            utilbill_doc.update({
                'sequence': sequence_and_version[0],
                'version': sequence_and_version[1],
            })

        utilbill_doc = bson_convert(copy.deepcopy(utilbill_doc))
        self.utilbills_collection.save(utilbill_doc, safe=True)
        # TODO catch mongo's return value and raise MongoError

    def delete_reebill(self, reebill):
        '''Deletes the document corresponding to the given state.ReeBill. Does
        not check if the reebill has been issued. No utility bill documents are
        deleted, even if there are frozen utility bill documents for this
        reebill, because only issued reebills have those and issued reebills
        should not be deleted.'''
        result = self.reebills_collection.remove({
            '_id.account': reebill.customer.account,
            '_id.sequence': reebill.sequence,
            '_id.version': reebill.version,
        }, safe=True)
        check_error(result)

