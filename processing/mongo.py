#!/usr/bin/env python
import sys
import datetime
from datetime import date, time, datetime
import pymongo
import bson # part of pymongo package
from operator import itemgetter
import itertools as it
import copy
from copy import deepcopy
from itertools import chain
from collections import defaultdict
import tsort
from billing.util.mongo_utils import bson_convert, python_convert, format_query, check_error
from billing.util.dictutils import deep_map, subdict, dict_merge
from billing.util.dateutils import date_to_datetime
from billing.processing.session_contextmanager import DBSession
from billing.processing.state import Customer, UtilBill
from billing.processing.exceptions import NoSuchBillException, \
    NotUniqueException, IssuedBillError, MongoError, FormulaError, RSIError, \
    NoRSIError
from billing.processing.rate_structure2 import RateStructure
import pprint
from sqlalchemy.orm.exc import NoResultFound
pp = pprint.PrettyPrinter(indent=1).pprint
sys.stdout = sys.stderr

# utility bill-to-reebill address schema converters
# also remember that utilbill and reebill use different names for these

def utilbill_billing_address_to_reebill_address(billing_address):
    '''Transforms Rich's utility bill billing address schema to his reebill
    address schema (which is the same for both kinds of addresses).'''
    return {
        ('ba_postal_code' if key == 'postalcode'
            else ('ba_street1' if key == 'street'
                else 'ba_' + key)): value
        for (key, value) in billing_address.iteritems()
    }

def utilbill_service_address_to_reebill_address(service_address):
    '''Transforms Rich's utility bill service address schema to his reebill
    address schema (which is the same for both kinds of addresses).'''
    return {
        ('sa_postal_code' if key == 'postalcode'
            else ('sa_street1' if key == 'street'
                else 'sa_' + key)): value
        for (key, value) in service_address.iteritems()
    }


def reebill_address_to_utilbill_address(address):
    '''Transforms any reebill address to utility bill address.'''
    return {
            (key[3:-1] if key[-7:] == 'street1'
                else ('postal_code' if key[3:] == 'postal_code'
                    else key[3:])): value
        for (key, value) in address.iteritems()
    }

# type-conversion functions

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


# NOTE deperecated; avoid using this if at all possible
def flatten_chargegroups_dict(chargegroups):
    flat_charges = []
    for (chargegroup, charges) in chargegroups.items(): 
        for charge in charges:
            charge['chargegroup'] = chargegroup
            flat_charges.append(charge)
    return flat_charges

# NOTE deperecated; avoid using this if at all possible
def unflatten_chargegroups_list(flat_charges):
    new_chargegroups = {}
    for cg, charges in it.groupby(sorted(flat_charges, key=lambda
            charge:charge['chargegroup']),
            key=lambda charge:charge['chargegroup']):
        new_chargegroups[cg] = []
        for charge in charges:
            del charge['chargegroup']
            new_chargegroups[cg].append(charge)
    return new_chargegroups

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


# TODO make this a method of a utility bill document class when one exists
def get_charges_json(utilbill_doc):
    '''Returns list of dictionaries describing charges for use in web browser.
    '''
    return [dict_merge(c, {'id': c['rsi_binding']})
            for c in utilbill_doc['charges']]

# TODO make this a method of a utility bill document class when one exists
def get_service_address(utilbill_doc):
    return utilbill_doc['service_address']

# TODO rename to get_meter_read_period
# TODO make this a method of a utility bill document class when one exists
def meter_read_period(utilbill_doc):
    '''Returns the period dates of the first (i.e. only) meter in this bill.
    '''
    assert len(utilbill_doc['meters']) >= 1
    meter = utilbill_doc['meters'][0]
    return meter['prior_read_date'], meter['present_read_date']

# TODO make this a method of a utility bill document class when one exists
def set_meter_read_period(utilbill_doc, start, end):
    '''Sets the period dates of the first (i.e. only) meter in this bill.
    '''
    assert len(utilbill_doc['meters']) >= 1
    meter = utilbill_doc['meters'][0]
    meter['prior_read_date'], meter['present_read_date'] = start, end

# TODO make this a method of a utility bill document class when one exists
def refresh_charges(utilbill_doc, uprs):
    '''Replaces charges in the utility bill document with newly-created ones
    based on the Rate Structure Items in 'uprs'. A charge is created
    for every RSI. The charges are computed according to the rate structures.
    '''
    utilbill_doc['charges'] = [{
        'rsi_binding': rsi.rsi_binding,
        'quantity': 0,
        'quantity_units': rsi.quantity_units,
        'rate': 0,
        'total': 0,
        'description': rsi.description,
        'group': rsi.group,
    } for rsi in sorted(uprs.rates, key=itemgetter('rsi_binding'))
            if rsi.has_charge]

def _validate_charges(utilbill_doc, rate_structure):
    '''Raises a NoRSIError if any charge in 'utilbill_doc doesn't correspond to
    a RateStructureItem in 'rate_structure'.
    '''
    rsi_bindings = set(rsi['rsi_binding'] for rsi in rate_structure.rates)
    for charge in utilbill_doc['charges']:
        if charge['rsi_binding'] not in rsi_bindings:
            raise NoRSIError('No rate structure item for "%s"' %
                           charge['rsi_binding'])

def _get_charge_by_rsi_binding(utilbill_doc, rsi_binding):
    matches = [c for c in utilbill_doc['charges']
            if c['rsi_binding'] ==  rsi_binding]
    assert len(matches) == 1
    return matches[0]

def update_charge(utilbill_doc, rsi_binding, fields):
    '''Modify the charge given by 'rsi_binding' by setting key-value pairs
    to match the dictionary 'fields'.
    '''
    charge = _get_charge_by_rsi_binding(utilbill_doc, rsi_binding)
    charge.update(fields)

def delete_charge(utilbill_doc, rsi_binding):
    for charge in utilbill_doc['charges']:
        if charge['rsi_binding'] == rsi_binding:
            utilbill_doc['charges'].remove(charge)
            return
    raise ValueError('RSI binding "%s" not found' % rsi_binding)

# TODO make this a method of a utility bill document class when one exists
# (if it doesn't go away first)
def add_charge(utilbill_doc, group_name):
    '''Add a new charge to the given utility bill with charge group "group_name"
    and default value for all its fields.
    '''
    utilbill_doc['charges'].append({
        'rsi_binding': 'RSI binding required',
        'description': 'description required',
        'quantity': 0,
        'quantity_units': 'kWh',
        'rate': 0,
        'total': 0,
        'group': group_name,
    })

# TODO make this a method of a utility bill document class when one exists
def compute_all_charges(utilbill_doc, uprs):
    '''Updates "quantity", "rate", and "total" fields in all charges in this
    utility bill document so they're correct according to the formulas in the
    RSIs in the given rate structures.
    '''
    # catch any type errors in the rate structure document up front to avoid
    # confusing error messages later
    uprs.validate()

    rate_structure = uprs
    rsis = rate_structure.rates

    # complain if any charge has an rsi_binding that does not match an RSI
    _validate_charges(utilbill_doc, rate_structure)

    # identifiers in RSI formulas are of the form "NAME.{quantity,rate,total}"
    # (where NAME can be a register or the RSI_BINDING of some other charge).
    # these are not valid python identifiers, so they can't be parsed as
    # individual names. this dictionary maps names to "quantity"/"rate"/"total"
    # to float values; RateStructureItem.compute_charge uses it to get values
    # for the identifiers in the RSI formulas. it is initially filled only with
    # register names, and the inner dictionary corresponding to each register
    # name contains only "quantity".
    identifiers = defaultdict(lambda:{})
    for meter in utilbill_doc['meters']:
        for register in meter['registers']:
            identifiers[register['register_binding']]['quantity'] = \
                    register['quantity']

    # get dictionary mapping rsi_bindings names to the indices of the
    # corresponding RSIs in an alphabetical list. 'rsi_numbers' assigns a number
    # to each.
    rsi_numbers = {rsi.rsi_binding: index for index, rsi in enumerate(rsis)}

    # the dependencies of some RSIs' formulas on other RSIs form a
    # DAG, which will be represented as a list of pairs of RSI numbers in
    # 'rsi_numbers'. this list will be used to determine the order
    # in which charges get computed. to build the list, find all identifiers
    # in each RSI formula that is not a register name; every such identifier
    # must be the name of an RSI, and its presence means the RSI whose
    # formula contains that identifier depends on the RSI whose rsi_binding is
    # the identifier.
    dependency_graph = []
    # the list 'independent_rsi_numbers' initially contains all RSI
    # numbers, and by the end of the loop will contain only the numbers of
    # RSIs that have no relationship to another one
    independent_rsi_numbers = set(rsi_numbers.itervalues())
    for rsi in rsis:
        this_rsi_num = rsi_numbers[rsi.rsi_binding]

        # for every node in the AST of the RSI's "quantity" and "rate"
        # formulas, if the 'ast' module labels that node as an
        # identifier, and its name does not occur in 'identifiers' above
        # (which contains only register names), add the tuple (this
        # charge's number, that charge's number) to 'dependency_graph'.
        for identifier in rsi.get_identifiers():
            if identifier in identifiers:
                continue
            try:
                other_rsi_num = rsi_numbers[identifier]
            except KeyError:
                # TODO might want to validate identifiers before computing
                # for clarity
                raise FormulaError(('Unknown variable in formula of RSI '
                        '"%s": %s') % (rsi.rsi_binding, identifier))
            # a pair (x,y) means x precedes y, i.e. y depends on x
            dependency_graph.append((other_rsi_num, this_rsi_num))
            independent_rsi_numbers.discard(other_rsi_num)
            independent_rsi_numbers.discard(this_rsi_num)

    # charges that don't depend on other charges can be evaluated before ones
    # that do.
    evaluation_order = list(independent_rsi_numbers)

    # 'evaluation_order' now contains only the indices of charges that don't
    # have dependencies. topological sort the dependency graph to find an
    # evaluation order that works for the charges that do have dependencies.
    try:
        evaluation_order.extend(tsort.topological_sort(dependency_graph))
    except tsort.GraphError as g:
        # if the graph contains a cycle, provide a more comprehensible error
        # message with the charge numbers converted back to names
        names_in_cycle = ', '.join(all_rsis[i]['rsi_binding'] for i in
                g.args[1])
        raise RSIError('Circular dependency: %s' % names_in_cycle)

    assert len(evaluation_order) == len(rsis)

    all_charges = sorted(utilbill_doc['charges'],
            key=lambda charge: charge['rsi_binding'])

    assert len(evaluation_order) == len(rsis)

    # compute each charge, using its corresponding RSI, in the order described
    # by 'evaluation_order'. every time a charge is computed, store the
    # resulting "quantity", "rate", and "total" in 'identifiers' so it can be
    # used in evaluating subsequent charges that depend on it.
    for rsi_number in evaluation_order:
        # compute the RSI regardless of whether there is really a charge
        # corresponding to it
        rsi = rsis[rsi_number]
        quantity, rate = rsi.compute_charge(identifiers)
        total = quantity * rate

        # if there is a charge update its "quantity", "rate', and "total"
        # fields
        try:
            charge = next(c for c in all_charges
                    if c['rsi_binding'] == rsi.rsi_binding)
        except StopIteration:
            # this RSI has no charge corresponding to it
            pass
        else:
            charge.update({
                'quantity': quantity,
                'rate': rate,
                'total': total,
                'description': rsi['description']
            })

        # update 'identifiers' so the results of this computation can be used
        # as identifier values in other RSIs
        identifiers[rsi.rsi_binding]['quantity'] = quantity
        identifiers[rsi.rsi_binding]['rate'] = rate
        identifiers[rsi.rsi_binding]['total'] = total

# TODO make this a method of a utility bill document class when one exists
def total_of_all_charges(utilbill_doc):
    '''Returns sum of "total" fields of all charges in the utility bill.
    '''
    # TODO: use method on SQLAlchemy UtilBill object to return this (or None
    # for a hypothetical utility bill). It can't be done here because 'state'
    # is not stored in the Mongo document.
    return sum(charge.get('total', 0) for charge in utilbill_doc['charges'])

class MongoReebill(object):

    @classmethod
    def _get_utilbill_subdoc(cls, utilbill_doc):
        '''Returns a a dictionary that is the subdocument of a reebill document
        representing the "hypothetical" version of the given utility bill
        document.'''
        return {
            # the "id" field in the reebill subdocument identifies which
            # utility bill it is associated with; this should match the the
            # value in the "document_id" column of the row of the
            # utilbill_reebill table in MySQL representing the association
            # between this reebill and the utility bill, and the "_id" of the
            # corresponding utility bill document.
            'id': utilbill_doc['_id'],

            # subdocuments corresponding to the the registers in the meters
            # of the utility bill: for now, all registers get included,
            # but in the future this could change.
            'shadow_registers': [{
                # 'register_binding' matches up this subdocument with a
                # utility bill register
                'register_binding': r['register_binding'],
                # hypothetical quantity of the corresponding utility bill
                # register
                'quantity': 0,
                # OLAP measure name that will be used for determining the
                # hypothetical quantity above
                'measure': 'Energy Sold'
            } for r in chain.from_iterable(m['registers']
                    for m in utilbill_doc['meters'])],

            # hypothetical charges are the same as actual (on the utility
            # bill); they will not reflect the renewable energy quantity until
            # computed
            'hypothetical_charges': utilbill_doc['charges'],
        }

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
        # NOTE currently only one utility bill is allowed
        assert len(utilbill_docs) == 1
        utilbill = utilbill_docs[0]

        reebill_doc = {
            "_id" : {
                "account" : account,
                "sequence" : sequence,
                "version" : version,
            },
            "utilbills" : [cls._get_utilbill_subdoc(u) for u in utilbill_docs],
        }
        return MongoReebill(reebill_doc, utilbill_docs)

    def __init__(self, reebill_data, utilbill_dicts):
        assert isinstance(reebill_data, dict)
        # defensively copy whatever is passed in; who knows where the caller got it from
        self.reebill_dict = copy.deepcopy(reebill_data)
        self._utilbills = copy.deepcopy(utilbill_dicts)

    def update_utilbill_subdocs(self, discount_rate):
        '''Refreshes the "utilbills" sub-documents of the reebill document to
        match the utility bill documents in _utilbills. (These represent the
        "hypothetical" version of each utility bill.)
        '''
        # TODO maybe this should be done in compute_bill or a method called by
        # it; see https://www.pivotaltracker.com/story/show/51581067
        # also might want to merge this with compute_charges below.
        self.reebill_dict['utilbills'] = \
                [MongoReebill._get_utilbill_subdoc(utilbill_doc) for
                utilbill_doc in self._utilbills]

    # NOTE avoid using this if at all possible,
    # because MongoReebill._utilbills will go away
    def get_total_utility_charges(self):
        return sum(total_of_all_charges(self._get_utilbill_for_handle(
            subdoc)) for subdoc in self.reebill_dict['utilbills'])

    # NOTE avoid using this if at all possible,
    # because MongoReebill._utilbills will go away
    def get_all_hypothetical_charges(self):
        ''' Returns all "hypothetical" versions of all charges, sorted
            alphabetically by group and rsi_binding
        '''
        assert len(self.reebill_dict['utilbills']) == 1
        return sorted((charge for subdoc in self.reebill_dict['utilbills']
                       for charge in subdoc['hypothetical_charges']),
                            key=itemgetter('group','rsi_binding'))

    def get_total_hypothetical_charges(self):
        '''Returns sum of "hypothetical" versions of all charges.
        '''
        # NOTE extreme tolerance for malformed data is required to acommodate
        # old bills; see https://www.pivotaltracker.com/story/show/66177446
        return sum(sum(charge.get('total', 0)
                for charge in subdoc['hypothetical_charges'])
                for subdoc in self.reebill_dict['utilbills'])

    def compute_charges(self, uprs):
        '''Recomputes hypothetical versions of all charges based on the
        associated utility bill.
        '''
        # process rate structures for all services
        for service in self.services:
            utilbill_doc = self._get_utilbill_for_service(service)
            compute_all_charges(utilbill_doc, uprs)

            # TODO temporary hack: duplicate the utility bill, set its register
            # quantities to the hypothetical values, recompute it, and then
            # copy all the charges back into the reebill
            hypothetical_utilbill = deepcopy(self._get_utilbill_for_service(
                    service))

            # these three generators iterate through "actual registers" of the
            # real utility bill (describing conventional energy usage), "shadow
            # registers" of the reebill (describing renewable energy usage
            # offsetting conventional energy), and "hypothetical registers" in
            # the copy of the utility bill (which will be set to the sum of the
            # other two).
            actual_registers = chain.from_iterable(m['registers']
                    for m in utilbill_doc['meters'])
            shadow_registers = chain.from_iterable(u['shadow_registers']
                    for u in self.reebill_dict['utilbills'])
            hypothetical_registers = chain.from_iterable(m['registers'] for m
                    in hypothetical_utilbill['meters'])

            # set the quantity of each "hypothetical register" to the sum of
            # the corresponding "actual" and "shadow" registers.
            for h_register in hypothetical_registers:
                a_register = next(r for r in actual_registers
                        if r['register_binding'] == 
                        h_register['register_binding'])
                s_register = next(r for r in shadow_registers
                        if r['register_binding'] == 
                        h_register['register_binding'])
                h_register['quantity'] = a_register['quantity'] + \
                        s_register['quantity']

            # compute the charges of the hypothetical utility bill
            compute_all_charges(hypothetical_utilbill, uprs)

            # copy the charges from there into the reebill
            self.reebill_dict['utilbills'][0]['hypothetical_charges'] = \
                    hypothetical_utilbill['charges']

    # TODO should _id fields even have setters? they're never supposed to
    # change.
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
    
    # Periods are read-only on the basis of which utilbills have been attached
    @property
    def period_begin(self):
        return min([self._get_utilbill_for_service(s)['start'] for s in self.services])
    @property
    def period_end(self):
        return max([self._get_utilbill_for_service(s)['end'] for s in self.services])
    def _utilbill_ids(self):
        '''Useful for debugging.'''
        # note order is not guranteed so the result may look weird
        return zip([h['id'] for h in self.reebill_dict['utilbills']],
                [u['_id'] for u in self._utilbills])

    def _get_utilbill_for_service(self, service):
        '''Returns utility bill document having the given service. There must
        be exactly one.'''
        matching_utilbills = [u for u in self._utilbills if u['service'] ==
                service]
        if len(matching_utilbills) == 0:
            raise ValueError('No utilbill found for service "%s"' % service)
        if len(matching_utilbills) > 1:
            raise ValueError('Multiple utilbills found for service "%s"' % service)
        return matching_utilbills[0]

    def _get_handle_for_service(self, service):
        '''Returns internal 'utibills' subdictionary whose corresponding
        utility bill has the given service. There must be exactly 1.'''
        u = self._get_utilbill_for_service(service)
        handles = [h for h in self.reebill_dict['utilbills'] if h['id'] ==
                u['_id']]
        if len(handles) == 0:
            raise ValueError(('Reebill has no reference to utilbill for '
                    'service "%s"') % service)
        if len(handles) > 1:
            raise ValueError(('Reebil has mulutple references to utilbill '
                    'for service "%s"' % service))
        return handles[0]

    def _get_utilbill_for_handle(self, utilbill_handle):
        '''Returns the utility bill dictionary whose _id correspinds to the
        "id" in the given internal utilbill dictionary.'''
        # i am calling each subdocument in the "utilbills" list (which contains
        # the utility bill's _id and data related to that bill) a "handle"
        # because it is what you use to grab a utility bill and it's kind of
        # like a pointer.
        id = utilbill_handle['id']
        matching_utilbills = [u for u in self._utilbills if u['_id'] == id]
        if len(matching_utilbills) == 0:
            raise ValueError('No utilbill found for id "%s"' % id)
        if len(matching_utilbills) > 1:
            raise ValueError('Multiple utilbills found for id "%s"' % id)
        return matching_utilbills[0]

    def _get_utilbill_for_rs(self, utility, service, rate_class):
        '''Returns the utility bill dictionary with the given utility name and
        rate structure name.'''
        matching_utilbills = [u for u in self._utilbills if u['utility'] ==
                utility and u['service'] == service and
                u['rate_structure_binding'] == rate_class]
        if len(matching_utilbills) == 0:
            raise ValueError(('No utilbill found for utility "%s", rate'
                    'structure "%s"') % (utility, rate_class))
        if len(matching_utilbills) > 1:
            raise ValueError(('Multiple utilbills found for utility "%s", rate'
                    'structure "%s"') % (utility, rate_class))
        return matching_utilbills[0]

    def get_all_shadow_registers_json(self):
        '''Given a utility bill document, returns a list of dictionaries describing
        registers of all meters.'''
        assert len(self.reebill_dict['utilbills']) == 1
        result = []
        for register in self.reebill_dict['utilbills'][0]['shadow_registers']:
                result.append({
                    'measure': register['measure'],
                    'register_binding': register['register_binding'],
                    'quantity': register['quantity']
                })
        return result

    @property
    def services(self):
        '''Returns a list of all services for which there are utilbills.'''
        return [u['service'] for u in self._utilbills if u['service'] not in self.suspended_services]

    @property
    def suspended_services(self):
        '''Returns list of services for which billing is suspended (e.g.
        because the customer has switched to a different fuel for part of the
        year). Utility bills for this service should be ignored in the attach
        operation.'''
        return self.reebill_dict.get('suspended_services', [])

    # TODO remove, since this feature is dead
    def suspend_service(self, service):
        '''Adds 'service' to the list of suspended services. Returns True iff
        it was added, False if it already present.'''
        service = service.lower()
        if service not in [s.lower() for s in self.services]:
            raise ValueError('Unknown service %s: services are %s' % (service, self.services))

        if 'suspended_services' not in self.reebill_dict:
            self.reebill_dict['suspended_services'] = []
        if service not in self.reebill_dict['suspended_services']:
            self.reebill_dict['suspended_services'].append(service)

    # TODO remove, since this feature is dead
    def resume_service(self, service):
        '''Removes 'service' from the list of suspended services. Returns True
        iff it was removed, False if it was not present.'''
        service = service.lower()
        if service not in [s.lower() for s in self.services]:
            raise ValueError('Unknown service %s: services are %s' % (service, self.services))

        if service in self.reebill_dict.get('suspended_services', {}):
            self.reebill_dict['suspended_services'].remove(service)
            # might as well take out the key if the list is empty
            if self.reebill_dict['suspended_services'] == []:
                del self.reebill_dict['suspended_services']

    def renewable_energy_period(self):
        '''Returns 2-tuple of dates (inclusive start, exclusive end) describing
        the period of renewable energy consumption in this bill. In practice,
        this means the read dates of the only meter in the utility bill which
        is equivalent to the utility bill's period.'''
        assert len(self._utilbills) == 1
        return meter_read_period(self._utilbills[0])

    def set_hypothetical_register_quantity(self, register_binding,
                    new_quantity):
        ''' Sets the "quantity" field of the given register subdocument to the
        given value, assumed to be in BTU for thermal and kW for PV.
        When stored, this quantity is converted to the same unit as the
        corresponding utility bill register.
        '''
        assert isinstance(new_quantity, float)

        # NOTE this may choose the wrong utility bill register if there are
        # multiple utility bills
        assert len(self.reebill_dict['utilbills']) == 1

        # look up corresponding utility bill register to get unit
        utilbill = self._utilbills[0]
        utilbill_register = next(chain.from_iterable((r for r in m['registers']
                if r['register_binding'] == register_binding)
                for m in utilbill['meters']))
        unit = utilbill_register['quantity_units'].lower()

        # Thermal: convert quantity to therms according to unit, and add it to
        # the total
        if unit == 'therms':
            new_quantity /= 1e5
        elif unit == 'btu':
            # TODO physical constants must be global
            pass
        elif unit == 'kwh':
            # TODO physical constants must be global
            new_quantity /= 1e5
            new_quantity /= .0341214163
        elif unit == 'ccf':
            # deal with non-energy unit "CCF" by converting to therms with
            # conversion factor 1
            # TODO: 28825375 - need the conversion factor for this
            print ("Register in reebill %s-%s-%s contains gas measured "
                   "in ccf: energy value is wrong; time to implement "
                   "https://www.pivotaltracker.com/story/show/28825375") \
                  % (self.account, self.sequence, self.version)
            new_quantity /= 1e5
        # PV: Unit is kilowatt; no conversion needs to happen
        elif unit == 'kwd':
            pass
        else:
            raise ValueError('Unknown energy unit: "%s"' % unit)

        all_hypo_registers = chain.from_iterable(u['shadow_registers'] for u
                in self.reebill_dict['utilbills'])
        register_subdoc = next(r for r in all_hypo_registers
                if r['register_binding'] == register_binding)
        register_subdoc['quantity'] = new_quantity

    def total_renewable_energy(self, ccf_conversion_factor=None):
        # TODO eliminate duplicate code with set_hypothetical_register_quantity
        assert ccf_conversion_factor is None or isinstance(
                ccf_conversion_factor, float)
        total_therms = 0
        for utilbill_handle in self.reebill_dict['utilbills']:
            for register_subdoc in utilbill_handle['shadow_registers']:
                quantity = register_subdoc['quantity']

                # look up corresponding utility bill register to get unit
                utilbill = self._get_utilbill_for_handle(utilbill_handle)
                utilbill_register = next(chain.from_iterable(
                        (r for r in m.get('registers', [])
                        if r.get('register_binding', None) == \
                        register_subdoc.get('register_binding', ''))
                        for m in utilbill.get('meters', [])))
                unit = utilbill_register['quantity_units'].lower()

                # convert quantity to therms according to unit, and add it to
                # the total
                if unit == 'therms':
                    total_therms += quantity
                elif unit == 'btu':
                    # TODO physical constants must be global
                    total_therms += quantity / 100000.0
                elif unit == 'kwh':
                    # TODO physical constants must be global
                    total_therms += quantity / .0341214163
                elif unit == 'ccf':
                    if ccf_conversion_factor is not None:
                        total_therms += quantity * ccf_conversion_factor
                    else:
                        # TODO: 28825375 - need the conversion factor for this
                        print ("Register in reebill %s-%s-%s contains gas measured "
                               "in ccf: energy value is wrong; time to implement "
                               "https://www.pivotaltracker.com/story/show/28825375") \
                              % (self.account, self.sequence, self.version)
                        # assume conversion factor is 1
                        total_therms += quantity
                elif unit =='kwd':
                    total_therms += quantity
                else:
                    raise ValueError('Unknown energy unit: "%s"' % unit)

        return total_therms

class ReebillDAO(object):
    '''A "data access object" for reading and writing reebills in MongoDB.'''

    def __init__(self, state_db, database, **kwargs):
        self.state_db = state_db
        self.reebills_collection = database['reebills']
        self.utilbills_collection = database['utilbills']

    def _get_version_query(self, account, sequence, specifier):
        '''Returns the version part of a Mongo query for a reebill based on the
        "version specifier": .'''

        # TODO
        if isinstance(specifier, date):
            raise NotImplementedError

        raise ValueError('Unknown version specifier "%s"' % specifier)

    def load_utilbills(self, **kwargs):
        '''Loads 0 or more utility bill documents from Mongo, returns a list of
        the raw dictionaries ordered by start date.

        kwargs (any of these added will be added to the query:
        account
        service
        utility
        start
        end
        sequence
        version
        '''
        #check individually for each allowed key in case extra things get thrown into kwargs
        query = {}
        if kwargs.has_key('account'):
            query.update({'account': kwargs['account']})
        if kwargs.has_key('utility'):
            query.update({'utility': kwargs['utility']})
        if kwargs.has_key('service'):
            query.update({'service': kwargs['service']})
        if kwargs.has_key('start'):
            query.update({'start': date_to_datetime(kwargs['start'])})
        if kwargs.has_key('end'):
            query.update({'end': date_to_datetime(kwargs['end'])})
        if kwargs.has_key('sequence'):
            query.update({'sequence': kwargs['sequence']})
        if kwargs.has_key('version'):
            query.update({'version': kwargs['version']})
        cursor = self.utilbills_collection.find(query, sort=[('start',
                pymongo.ASCENDING)])
        return list(cursor)

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
            # querying for None datetimes should work
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
        # TODO add reebill argument here like above?
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

    def _load_all_utillbills_for_reebill(self, session, reebill_doc):
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


            # convert types
            utilbill_doc = convert_datetimes(utilbill_doc)

            result.append(utilbill_doc)

        return result


    def load_reebill(self, account, sequence, version='max'):
        '''Returns the reebill with the given account and sequence, and the a
        version: a specific version number, an issue date (before which the
        greatest issued version is returned, and after which the greatest
        overall version is returned), or 'max', which specifies the greatest
        version overall.'''
        # NOTE not using context manager here because it commits the
        # transaction when the session exits! this method should be usable
        # inside other transactions.
        session = self.state_db.session()

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
                    max_version = self.state_db.max_version(session, account,
                            sequence)
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

        # load utility bills
        utilbill_docs = self._load_all_utillbills_for_reebill(session, mongo_doc)

        mongo_reebill = MongoReebill(mongo_doc, utilbill_docs)
        return mongo_reebill

    def load_reebills_for(self, account, version='max'):
        if not account: return None
        # NOTE not using context manager (see comment in load_reebill)
        session = self.state_db.session()
        sequences = self.state_db.listSequences(session, account)
        return [self.load_reebill(account, sequence, version) for sequence in sequences]
    
    def load_reebills_in_period(self, account=None, version=0, start_date=None,
            end_date=None, include_0=False):
        '''Returns a list of MongoReebills whose period began on or before
        'end_date' and ended on or after 'start_date' (i.e. all bills between
        those dates and all bills whose period includes either endpoint). The
        results are ordered by sequence. If 'start_date' and 'end_date' are not
        given or are None, the time period extends to the begining or end of
        time, respectively. Sequence 0 is never included.
        
        'version' may be a specific version number, or 'any' to get all
        versions.'''
        with DBSession(self.state_db) as session:
            query = {}
            if account is not None:
                query['_id.account'] = account
            if isinstance(version, int):
                query.update({'_id.version': version})
            elif version == 'any':
                pass
            elif version == 'max':
                # TODO max version (it's harder than it looks because you don't
                # have the account or sequence of a specific reebill to query
                # MySQL for here)
                raise NotImplementedError
            else:
                raise ValueError('Unknown version specifier "%s"' % version)
            if not include_0:
                query['_id.sequence'] = {'$gt': 0}

            # add dates to query if present (converting dates into datetimes
            # because mongo only allows datetimes)
            if start_date is not None:
                start_datetime = datetime(start_date.year, start_date.month,
                        start_date.day)
                query['period_end'] = {'$gte': start_datetime}
            if end_date is not None:
                end_datetime = datetime(end_date.year, end_date.month,
                        end_date.day)
                query['period_begin'] = {'$lte': end_datetime}
            result = []
            docs = self.reebills_collection.find(query).sort('sequence')
            for mongo_doc in self.reebills_collection.find(query):
                mongo_doc = convert_datetimes(mongo_doc)
                utilbill_docs = self._load_all_utillbills_for_reebill(session, mongo_doc)
                result.append(MongoReebill(mongo_doc, utilbill_docs))
            return result

    def save_reebill(self, reebill, force=False):
        '''Saves the given reebill document.

        Replacing an already-issued reebill (as determined by StateDB) or its
        utility bills is forbidden unless 'force' is True (this should only be
        used for testing).
        '''
        session = self.state_db.session()
        issued = self.state_db.is_issued(session, reebill.account,
                 reebill.sequence, version=reebill.version, nonexistent=False)
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

