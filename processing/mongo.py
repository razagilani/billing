#!/usr/bin/env python
import sys
import datetime
from datetime import date, time, datetime
import pymongo
import bson # part of pymongo package
import functools
from urlparse import urlparse
import httplib
import string
import base64
import itertools as it
import copy
from copy import deepcopy
import uuid as UUID
from itertools import chain
from collections import defaultdict
from tsort import topological_sort
from billing.util.mongo_utils import bson_convert, python_convert, format_query, check_error
from billing.util.dictutils import deep_map, subdict
from billing.util.dateutils import date_to_datetime
from billing.processing.session_contextmanager import DBSession
from billing.processing.state import Customer, UtilBill
from billing.processing.exceptions import NoSuchBillException, NotUniqueException, NoRateStructureError, NoUtilityNameError, IssuedBillError, MongoError
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


# TODO believed to be needed only by presentation code, so put it there.
def flatten_chargegroups_dict(chargegroups):
    flat_charges = []
    for (chargegroup, charges) in chargegroups.items(): 
        for charge in charges:
            charge['chargegroup'] = chargegroup
            flat_charges.append(charge)
    return flat_charges

# TODO believed to be needed only by presentation code, so put it there.
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
    non-shadow registers of all meters. (The "actual" in the name has nothing
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
        "shadow" : False,
        "identifier" : identifier,
        "type" : "total",
        "register_binding": "Insert register binding here"
    }
    new_shadow_register = {
        "description" : "Insert description",
        "quantity" : 0,
        "quantity_units" : "therms",
        "shadow" : True,
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
                             " id %sj" %(register_id, original_meter_id))
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
        register['quantity'] = str(quantity)
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
def actual_chargegroups_flattened(utilbill_doc):
    return flatten_chargegroups_dict(copy.deepcopy(
            utilbill_doc['chargegroups']))

# TODO make this a method of a utility bill document class when one exists
def set_actual_chargegroups_flattened(utilbill_doc, flat_charges):
    utilbill_doc['chargegroups'] = unflatten_chargegroups_list(flat_charges)

def meter_read_period(utilbill_doc):
    '''Returns the period dates of the first (i.e. only) meter in this bill.'''
    assert len(utilbill_doc['meters']) >= 1
    meter = utilbill_doc['meters'][0]
    return meter['prior_read_date'], meter['present_read_date']

# TODO make this a method of a utility bill document class when one exists
def compute_all_charges(utilbill_doc, uprs, cprs):
    '''Updates "quantity", "rate", and "total" fields in all charges in this
    utility bill document so they're correct accoding to the formulas in the
    RSIs in the given rate structures. RSIs in 'uprs' that have the same
    'rsi_binding' as any RSI in 'cprs' are ignored.
    '''
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

    # get dictionary mapping rsi_bindings to RateStructureItem objects from
    # 'uprs', then replace any items in it with RateStructureItems from 'cprs'
    # with the same rsi_bindings
    rsis = uprs.rsis_dict()
    rsis.update(cprs.rsis_dict())

    # get dictionary mapping charge names to their indices in an alphabetical
    # list. this assigns a number to each charge.
    # TODO rename to charge_names_to_numbers
    all_charges = list(sorted(chain.from_iterable(
            utilbill_doc['chargegroups'].itervalues()),
            key=lambda charge: charge['rsi_binding']))
    charge_numbers = {charge['rsi_binding']: index for index, charge in
            enumerate(all_charges)}

    # the dependencies of some charges' RSI formulas on other charges form a
    # DAG, which will be represented as a list of pairs of charge numbers in
    # 'charge_numbers'. this list will be used to determine the order
    # in which charges get evaluated. to build the list, find all identifiers
    # in each RSI formula that is not a register name; every such identifier
    # must be the name of a charge, and its presence means the charge whose RSI
    # formula contains that identifier depends on the charge whose name is the
    # identifier.
    dependency_graph = []
    # this list initially contains all charge numbers, and by the end of the
    # loop will contain only the numbers of charges that had no relationship to
    # another chanrge
    independent_charge_numbers = set(charge_numbers.itervalues())
    for charges in utilbill_doc['chargegroups'].itervalues():
        for charge in charges:
            rsi = rsis[charge['rsi_binding']]
            this_charge_num = charge_numbers[charge['rsi_binding']]

            # for every node in the AST of the RSI's "quantity" and "rate"
            # formulas, if the 'ast' module identifiers that node as an
            # identifier, and its name does not occur in 'identifiers' above
            # (which contains only register names), add the tuple (this
            # charge's number, that charge's number) to 'dependency_graph'.
            for identifier in rsi.get_identifiers():
                if identifier in identifiers:
                    continue
                other_charge_num = charge_numbers[identifier]
                # a pair (x,y) means x precedes y, i.e. y depends on x
                dependency_graph.append((other_charge_num, this_charge_num))
                independent_charge_numbers.discard(other_charge_num)
                independent_charge_numbers.discard(this_charge_num)

    # charges that don't depend on other charges can be evaluated before ones
    # that do.
    evaluation_order = list(independent_charge_numbers)

    # 'evaluation_order' now contains only the indices of charges that don't
    # have dependencies. topological sort the dependency graph to find an
    # evaluation order that works for the charges that do have dependencies.
    try:
        evaluation_order.extend(topological_sort(dependency_graph))
    except GraphError as g:
        # if the graph contains a cycle, provide a more comprehensible error
        # message with the charge numbers converted back to names
        names_in_cycle = ', '.join(all_charges[i] for i in ge.args[1])
        raise ValueError('Circular dependency: %' % names_in_cycle)
    assert len(evaluation_order) == len(all_charges)

    # compute each charge, using its corresponding RSI, in the above order.
    # every time a charge is computed, store the resulting "quantity", "rate",
    # and "total" in 'identifiers' so it can be used in evaluating subsequent
    # charges that depend on it.
    for charge_number in evaluation_order:
        charge = all_charges[charge_number]
        rsi = rsis[charge['rsi_binding']]
        quantity, rate = rsi.compute_charge(identifiers)
        charge['quantity'] = quantity
        charge['rate'] = rate
        charge['total'] = quantity * rate
        identifiers[charge['rsi_binding']]['quantity'] = charge['quantity']
        identifiers[charge['rsi_binding']]['rate'] = charge['rate']
        identifiers[charge['rsi_binding']]['total'] = charge['total']

def total_of_all_charges(utilbill_doc):
    '''Returns sum of "total" fields of all charges in the utility bill.
    '''
    return sum(charge['total'] for charge in
            chain.from_iterable(utilbill_doc['chargegroups'].itervalues()))

class MongoReebill(object):
    '''Class representing the reebill data structure stored in MongoDB. All
    data is stored in 'dictionary', which is a Python dict that PyMongo could
    read/write directly from/to the database. Provides methods for extracting
    pieces of bill information.

    Design matters to work through:

        where type conversions occur - 
            Should only happen on load/save so that object references are not
            lost. 
            The lifecycle should be:  load from source converting to preferred
            python types.  Use class.  save to source converting to preferred
            source types.  
            This is in opposition to doing type conversion on getter/setter
            invocation.

        key naming in mongo: key names must be unique so that types can be properly
        translated to the preferred python type.  The function that translates the
        types does so recursively and it is desired the type mapping table be kept
        flat and uncomplicated otherwise we are going in the direction of enforc-
        ing a schema which is undesirable.

        dictionary style access: e.g. bill.statistics() - dict returned, key access
            In this case, consumer needs to select a default if the key is missing
            which is good because a missing key means different things to 
            different consumers. Dict.get(key, default) allows consumers to nicely
            contextulize a missing value.
            Consumers that need a missing key to be exceptional, than should 
            directly access they key.

        property style access: e.g. bill.account - scalar returned
            In this case, this code needs to select a default if the key is missing
            probably wan't some consistency

        property style access that returns a dictionary:
            Not sure this ever happens.

        This class should not include business logic, rather a helper should.
        This helper is process.py atm.

        This class should:
        - marshal and unmarshal data (e.g. flatten and nest charges)
        - convert types
        - localize
        - hide the underlying mongo document organization
        - return cross cutting sets of data (e.g. all registers when registers are grouped by meter)
    '''

    @classmethod
    def get_utilbill_subdoc(cls, utilbill_doc):
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

            # hypothetical versions of all the registers in all the meters of
            # the utility bill--though the only thing that should ever be
            # different from the real versions is the value of the "quantity"
            # key in each register
            'shadow_registers': list(chain.from_iterable(m['registers'] for m in
                    utilbill_doc['meters'])),

            # hypothetical charges are the same as actual (on the utility
            # bill); they will not reflect the renewable energy quantity until
            # computed
            'hypothetical_chargegroups': utilbill_doc['chargegroups'],

            'ree_charges': 0,
            'ree_savings': 0,
            'ree_value': 0
        }

    @classmethod
    def get_reebill_doc_for_utilbills(cls, account, sequence, version,
                discount_rate, late_charge_rate, utilbill_docs):
        '''Returns a newly-created MongoReebill object having the given account
        number, discount rate, late charge rate, and list of utility bill
        documents. Hypothetical charges are the same as the utility bill's
        actual charges. Addresses are copied from the utility bill template.
        Note that the utility bill document _id is not changed; the caller is
        responsible for properly duplicating utility bill documents.'''
        # NOTE currently only one utility bill is allowed
        assert len(utilbill_docs) == 1
        utilbill = utilbill_docs[0]

        reebill_doc = {
            "_id" : {
                "account" : account,
                "sequence" : sequence,
                "version" : version,
            },
            "ree_charges" : 0,
            "ree_value" : 0,
            "discount_rate" : discount_rate,
            'late_charge_rate': late_charge_rate,
            'late_charges': 0,
            "message" : None,
            "issue_date" : None,
            "utilbills" : [cls.get_utilbill_subdoc(u) for u in utilbill_docs],
            "payment_received" : 0,
            "due_date" : None,
            "total_adjustment" : 0,
            "manual_adjustment" : 0,
            "ree_savings" : 0,
            #"statistics" : {
                #"renewable_utilization" : 0,
                #"renewable_produced" : None,
                #"total_conventional_consumed" : 0,
                #"total_co2_offset" : 0,
                #"conventional_consumed" : 0,
                #"total_renewable_produced" : None,
                #"total_savings" : 0,
                #"consumption_trend" : [
                    #{ "quantity" : 0, "month" : "Dec" },
                    #{ "quantity" : 0, "month" : "Jan" },
                    #{ "quantity" : 0, "month" : "Feb" },
                    #{ "quantity" : 0, "month" : "Mar" },
                    #{ "quantity" : 0, "month" : "Apr" },
                    #{ "quantity" : 0, "month" : "May" },
                    #{ "quantity" : 0, "month" : "Jun" },
                    #{ "quantity" : 0, "month" : "Jul" },
                    #{ "quantity" : 0, "month" : "Aug" },
                    #{ "quantity" : 0, "month" : "Sep" },
                    #{ "quantity" : 0, "month" : "Oct" },
                    #{ "quantity" : 0, "month" : "Nov" }
                #],
                #"conventional_utilization" : 0,
                #"total_trees" : 0,
                #"co2_offset" : 0,
                #"total_renewable_consumed" : 0,
                #"renewable_consumed" : 0,
            #},
            "balance_due" : 0,
            "prior_balance" : 0,
            #"hypothetical_total" : 0,
            "balance_forward" : 0,
            # NOTE these address fields are containers for utility bill
            # addresses. these addresses will eventually move into utility bill
            # documents, and if necessary new reebill-specific address fields
            # will be added. so copying the address from the utility bill to
            # the reebill is the correct thing (and there is only one utility
            # bill for now). see
            # https://www.pivotaltracker.com/story/show/47749247

            # copy addresses from utility bill
            # specifying keys explicitly to provide validation and to document
            # the schema
            "billing_address": {
                'addressee': utilbill['billing_address']['addressee'],
                'street': utilbill['billing_address']['street'],
                'city': utilbill['billing_address']['city'],
                'state': utilbill['billing_address']['state'],
                'postal_code': utilbill['billing_address']['postal_code'],
            },
            "service_address": {
                'addressee': utilbill['service_address']['addressee'],
                'street': utilbill['service_address']['street'],
                'city': utilbill['service_address']['city'],
                'state': utilbill['service_address']['state'],
                'postal_code': utilbill['service_address']['postal_code'],
            },
        }
        return MongoReebill(reebill_doc, utilbill_docs)


    def __init__(self, reebill_data, utilbill_dicts):
        assert isinstance(reebill_data, dict)
        # defensively copy whatever is passed in; who knows where the caller got it from
        self.reebill_dict = copy.deepcopy(reebill_data)
        self._utilbills = copy.deepcopy(utilbill_dicts)

    # TODO 36805917 clear() can go away when ReeBills can be constructed
    def clear(self):
        '''Code for clearing out fields of newly-rolled rebill and its utility
        bill documents (moved from __init__, called by Process.roll_bill). TODO
        remove this.'''
        # set start date of each utility bill in this reebill to the end date
        # of the previous utility bill for that service
        #for service in self.services:
        #    prev_start, prev_end = self.utilbill_period_for_service(service)
        #    self.set_utilbill_period_for_service(service, (prev_end, None))

        # process rebill
        self.total_adjustment = 0
        self.manual_adjustment = 0
        #self.hypothetical_total = 0
        self.ree_value = 0
        self.ree_charges = 0
        self.ree_savings = 0
        self.due_date = None
        self.issue_date = None
        self.motd = None

        # this should always be set from the value in MySQL, which holds the
        # "current" discount rate for each customer
        self.discount_rate = 0

        self.prior_balance = 0
        self.total_due = 0
        self.balance_due = 0
        self.payment_received = 0
        self.balance_forward = 0
        # some customers are supposed to lack late_charges key, some are
        # supposed to have late_charges: None, and others have
        # self.late_charges: 0
        if 'late_charges' in self.reebill_dict and self.late_charges is not None:
            self.late_charges = 0

        for service in self.services:
            # get utilbill numbers and zero them out
            self.set_actual_total_for_service(service, 0)
            self.set_hypothetical_total_for_service(service, 0)
            self.set_ree_value_for_service(service, 0)
            self.set_ree_savings_for_service(service, 0)
            self.set_ree_charges_for_service(service, 0)

            # set new UUID's & clear out the last bound charges
            actual_chargegroups = self.actual_chargegroups_for_service(service)
            for (group, charges) in actual_chargegroups.items():
                for charge in charges:
                    charge['uuid'] = str(UUID.uuid1())
                    if 'rate' in charge: del charge['rate']
                    if 'quantity' in charge: del charge['quantity']
                    if 'total' in charge: del charge['total']
                    
            self.set_actual_chargegroups_for_service(service, actual_chargegroups)

            hypothetical_chargegroups = self.hypothetical_chargegroups_for_service(service)
            for (group, charges) in hypothetical_chargegroups.items():
                for charge in charges:
                    charge['uuid'] = str(UUID.uuid1())
                    if 'rate' in charge: del charge['rate']
                    if 'quantity' in charge: del charge['quantity']
                    if 'total' in charge: del charge['total']
                    
            self.set_hypothetical_chargegroups_for_service(service, hypothetical_chargegroups)
       
            # reset measured usage
            for service in self.services:
                for meter in self.meters_for_service(service):
                    self.set_meter_read_date(service, meter['identifier'], None, meter['present_read_date'])
                for actual_register in self.actual_registers(service):
                    self.set_actual_register_quantity(actual_register['identifier'], 0)
                for shadow_register in self.shadow_registers(service):
                    self.set_shadow_register_quantity(shadow_register['identifier'], 0)

            # if these keys exist in the document, remove them
            for bad_key in 'statistics', 'actual_total', 'hypothetical_total':
                if bad_key in self.reebill_dict:
                    del self.reebill_dict[bad_key]


    def convert_to_new_account(self, account):
        # TODO: the existence of this function is a symptom of ugly design.
        # figure out how to make it go away if possible.
        # https://www.pivotaltracker.com/story/show/37798427
        '''Sets the account of this reebill and all its utility bills to
        'account', and creates new _ids in all utility bills and the reebill's
        references to them. And converts frozen utility bills into editable
        ones by removing the "sequence" and "version" keys, if present. Used
        for converting an existing reebill and its utility bills into a
        template for a new account.'''
        self.account = account
        for handle in self.reebill_dict['utilbills']:
            u = self._get_utilbill_for_handle(handle)
            u['account'] = account
            if 'sequence' in u:
                del u['sequence']
            if 'version' in u:
                del u['version']
            u['_id'] = handle['id'] = bson.ObjectId()

    # TODO: is this method obsolete?
    def new_utilbill_ids(self):
        '''Replaces _ids in utility bill documents and the reebill document's
        references to them, and removes "sequence" and "version" keys if
        present (to convert frozen utility bill into editable one). Used when
        rolling to create copies of the utility bills. does not need to be
        called when creating a new account because 'convert_to_new_account'
        also does this.'''
        for utilbill_handle in self.reebill_dict['utilbills']:
            utilbill_doc = self._get_utilbill_for_handle(utilbill_handle)
            new_id = bson.objectid.ObjectId()
            utilbill_handle['id'] = utilbill_doc['_id'] = new_id
            if 'sequence' in utilbill_doc:
                del utilbill_doc['sequence']
            if 'version' in utilbill_doc:
                del utilbill_doc['version']

    def update_utilbill_subdocs(self):
        '''Refreshes the "utilbills" sub-documents of the reebill document to
        match the utility bill documents in _utilbills. (These represent the
        "hypothetical" version of each utility bill.)'''
        # TODO maybe this should be done in compute_bill or a method called by
        # it; see https://www.pivotaltracker.com/story/show/51581067
        self.reebill_dict['utilbills'] = \
                [MongoReebill.get_utilbill_subdoc(utilbill_doc) for
                utilbill_doc in self._utilbills]

                
    def compute_charges(self, uprs, cprs):
        """This function binds a rate structure against the actual and
        hypothetical charges found in a bill. If and RSI specifies information
        no in the bill, it is added to the bill. If the bill specifies
        information in a charge that is not in the RSI, the charge is left
        untouched."""
        account, sequence = self.account, self.sequence

        # process rate structures for all services
        for service in self.services:
            utilbill_doc = self._get_utilbill_for_service(service)
            compute_all_charges(utilbill_doc, uprs, cprs)

            # TODO temporary hack: duplicate the utility bill, set its register
            # quantities to the hypothetical values, recompute it, and then
            # copy all the charges back into the reebill
            hypothetical_utilbill = deepcopy(self._get_utilbill_for_service(service))

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
                        h_register['quantity']

            # compute the charges of the hypothetical utility bill
            compute_all_charges(hypothetical_utilbill, uprs, cprs)

            # copy the charges from there into the reebill
            self.set_hypothetical_chargegroups_for_service(service,
                    hypothetical_utilbill['chargegroups'])






            ###
            ### All registers for all meters in a given service are made available
            ### to the rate structure for the given service.
            ### Registers that are not to be used by the rate structure should
            ### simply not have an rsi_binding.
            ###

            ### actual

            ### copy rate structure because it gets destroyed during use
            ##rate_structure = copy.deepcopy(the_rate_structure)

            ### get non-shadow registers in the reebill
            ##actual_register_readings = self.actual_registers(service)

            ###print "loaded rate structure"
            ###pp(rate_structure)

            ###print "loaded actual register readings"
            ###pp(actual_register_readings)

            ### copy the quantity of each non-shadow register in the reebill to
            ### the corresponding register dictionary in the rate structure
            ### ("apply the registers from the reebill to the probable rate structure")
            ##rate_structure.bind_register_readings(actual_register_readings) 
            ###print "rate structure with bound registers"
            ###pp(rate_structure)

            ### get all utility charges from the reebill's utility bill (in the
            ### form of a group name -> [list of charges] dictionary). for each
            ### charge, find the corresponding rate structure item (the one that
            ### matches its "rsi_binding") and copy the values of "description",
            ### "quantity", "quantity_units", "rate", and "rate_units" in that
            ### RSI to the charge
            ### ("process actual charges with non-shadow meter register totals")
            ### ("iterate over the charge groups, binding the reebill charges to
            ### its associated RSI")
            ##actual_chargegroups = self.actual_chargegroups_for_service(service)
            ##for charges in actual_chargegroups.values():
                ##rate_structure.bind_charges(charges)

            ### (original comment "don't have to set this because we modified the
            ### actual_chargegroups" is false--we modified the rate structure
            ### items, but left the charges in the bill unchanged. as far as i
            ### can tell this line of code has no effect)
            ##self.set_actual_chargegroups_for_service(service, actual_chargegroups)

            ## hypothetical charges

            ## re-copy rate structure because it gets destroyed during use
            #rate_structure = copy.deepcopy(the_rate_structure)

            ## get shadow and non-shadow registers in the reebill
            #actual_register_readings = self.actual_registers(service)
            #shadow_register_readings = self.shadow_registers(service)

            ## "add the shadow register totals to the actual register, and re-process"

            ## TODO: 12205265 Big problem here.... if REG_TOTAL, for example, is used to calculate
            ## a rate shown on the utility bill, it works - until REG_TOTAL has the shadow
            ## renewable energy - then the rate is calculated incorrectly.  This is because
            ## a seemingly innocent expression like SETF 2.22/REG_TOTAL.quantity calcs 
            ## one way for actual charge computation and another way for hypothetical charge
            ## computation.

            ## for each shadow register dictionary: add its quantity to the
            ## quantity of the corresponding non-shadow register
            #registers_to_bind = copy.deepcopy(shadow_register_readings)
            #for shadow_reading in registers_to_bind:
                #for actual_reading in actual_register_readings:
                    #if actual_reading['identifier'] == shadow_reading['identifier']:
                        #shadow_reading['quantity'] += actual_reading['quantity']
                ## TODO: throw exception when registers mismatch

            ## copy the quantity of each register dictionary in the reebill to
            ## the corresponding register dictionary in the rate structure
            ## ("apply the combined registers from the reebill to the probable
            ## rate structure")
            #rate_structure.bind_register_readings(registers_to_bind)

            ## for each hypothetical charge in the reebill, copy the values of
            ## "description", "quantity", "quantity_units", "rate", and
            ## "rate_units" from the corresponding rate structure item to the
            ## charge
            ## ("process hypothetical charges with shadow and non-shadow meter register totals")
            ## ("iterate over the charge groups, binding the reebill charges to its associated RSI")
            #hypothetical_chargegroups = self.hypothetical_chargegroups_for_service(service)
            #for chargegroup, charges in hypothetical_chargegroups.items():
                #rate_structure.bind_charges(charges)

            ## don't have to set this because we modified the hypothetical_chargegroups
            ##reebill.set_hypothetical_chargegroups_for_service(service, hypothetical_chargegroups)


    # methods for getting data out of the mongo document: these could change
    # depending on needs in render.py or other consumers. return values are
    # strings unless otherwise noted.
    
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
    
    @property
    def issue_date(self):
        """ This is a mandatory property of a ReeBill. Consequently, there is
        no information to be had by throwing a key exception on a missing
        issue_date.  """

        if 'issue_date' in self.reebill_dict:
            return python_convert(self.reebill_dict['issue_date'])

        return None

    @issue_date.setter
    def issue_date(self, value):
        self.reebill_dict['issue_date'] = value

    @property
    def due_date(self):
        return python_convert(self.reebill_dict['due_date'])
    @due_date.setter
    def due_date(self, value):
        self.reebill_dict['due_date'] = value

    # Periods are read-only on the basis of which utilbills have been attached
    @property
    def period_begin(self):
        return min([self._get_utilbill_for_service(s)['start'] for s in self.services])
    @property
    def period_end(self):
        return max([self._get_utilbill_for_service(s)['end'] for s in self.services])
    
    @property
    def discount_rate(self):
        return self.reebill_dict['discount_rate']
    @discount_rate.setter
    def discount_rate(self, value):
        self.reebill_dict['discount_rate'] = value

    @property
    def total(self):
        '''The sum of all charges on this bill that do not come from other
        bills, i.e. charges that are being charged to the customer's account on
        this bill's issue date. (This includes the late charge, which depends
        on another bill for its value but belongs to the bill on which it
        appears.) This total is what should be used to calculate the adjustment
        produced by the difference between two versions of a bill.'''
        # if/when more charges are added (e.g. "value-added charges") they
        # should be included here
        return self.ree_charges + (self.late_charges if 'late_charges' in
                self.reebill_dict else 0)

    @property
    def balance_due(self):
        '''Overall balance of the customer's account at the time this bill was
        issued, including unpaid charges from previous bills.
        '''
        return self.reebill_dict['balance_due']
    @balance_due.setter
    def balance_due(self, value):
        self.reebill_dict['balance_due'] = value

    @property
    def late_charge_rate(self):
        # currently, there is a population of reebills that do not have a late_charge_rate
        # because late_charge_rate was not yet implemented.
        # and since we may want to know this, let the key exception be raised.
        return self.reebill_dict['late_charge_rate']
    @late_charge_rate.setter
    def late_charge_rate(self, value):
        self.reebill_dict['late_charge_rate'] = value

    @property
    def late_charges(self):
        """ This is an optional property of a ReeBill.  There was a day where
        ReeBills were not part of a late charge program.  Consequently, we
        would want to present bills from the past without a late charge box in
        the UI.  So, an exception if they don't exist.  """
        return self.reebill_dict['late_charges']

    @late_charges.setter
    def late_charges(self, value):
        self.reebill_dict['late_charges'] = value

    @property
    def billing_address(self):
        '''Returns a dict.'''
        return self.reebill_dict['billing_address']
    @billing_address.setter
    def billing_address(self, value):
        self.reebill_dict['billing_address'] = value

    @property
    def service_address(self):
        '''Returns a dict.'''
        return self.reebill_dict['service_address']
    @service_address.setter
    def service_address(self, value):
        self.reebill_dict['service_address'] = value

    def service_address_formatted(self):
        try:
            return '%(street)s, %(city)s, %(state)s' % self.reebill_dict['service_address']
        except KeyError as e:
            print >> sys.stderr, 'Reebill %s-%s-%s service address lacks key "%s"' \
                    % (self.account, self.sequence, self.version, e)
            print >> sys.stderr, self.reebill_dict['service_address']
            return '?'

    @property
    def prior_balance(self):
        return self.reebill_dict['prior_balance']
    @prior_balance.setter
    def prior_balance(self, value):
        self.reebill_dict['prior_balance'] = value

    @property
    def payment_received(self):
        return self.reebill_dict['payment_received']

    @payment_received.setter
    def payment_received(self, value):
        self.reebill_dict['payment_received'] = value

    @property
    def total_adjustment(self):
        return self.reebill_dict['total_adjustment']
    @total_adjustment.setter
    def total_adjustment(self, value):
        self.reebill_dict['total_adjustment'] = value

    @property
    def manual_adjustment(self):
        return self.reebill_dict['manual_adjustment']
    @manual_adjustment.setter
    def manual_adjustment(self, value):
        self.reebill_dict['manual_adjustment'] = value

    @property
    def ree_charges(self):
        return self.reebill_dict['ree_charges']
    @ree_charges.setter
    def ree_charges(self, value):
        self.reebill_dict['ree_charges'] = value

    @property
    def ree_savings(self):
        return self.reebill_dict['ree_savings']
    @ree_savings.setter
    def ree_savings(self, value):
        self.reebill_dict['ree_savings'] = value

    @property
    def balance_forward(self):
        return self.reebill_dict['balance_forward']
    @balance_forward.setter
    def balance_forward(self, value):
        self.reebill_dict['balance_forward'] = value

    @property
    def motd(self):
        '''"motd" = "message of the day"; it's optional, so the reebill may not
        have one.'''
        return self.reebill_dict.get('message', '')
    @motd.setter
    def motd(self, value):
        self.reebill_dict['message'] = value

    # TODO this must die https://www.pivotaltracker.com/story/show/36492387
    @property
    def actual_total(self):
        '''Returns total of all charges of all utility bills belonging to this
        reebill.
        '''
        return sum(total_of_all_charges(u) for u in self._utilbills)

    @property
    def hypothetical_total(self):
        '''Returns total of all charges of all "hypothetical utility bill"
        subdocuments belongong to this reebill.
        '''
        return sum(sum(charge['total'] for charge in
            chain.from_iterable(subdoc['hypothetical_chargegroups'].itervalues()))
            for subdoc in self.reebill_dict['utilbills'])

    @property
    def ree_value(self):
        return self.reebill_dict['ree_value']
    @ree_value.setter
    def ree_value(self, value):
        self.reebill_dict['ree_value'] = value

    @property
    def bill_recipients(self):
        '''E-mail addresses of bill recipients.

        If these data exist, returns a list of strings. Otherwise, returns None.'''
        res = self.reebill_dict.get('bill_recipients', None)
        if res is None:
            self.reebill_dict['bill_recipients'] = []
            return self.reebill_dict['bill_recipients']
        return res
        
    @bill_recipients.setter
    def bill_recipients(self, value):
        '''Assigns a list of e-mail addresses representing bill recipients.'''
        self.reebill_dict['bill_recipients'] = value

    @property
    def last_recipients(self):
        '''E-mail addresses of bill recipients.

        If these data exist, returns a list of strings. Otherwise, returns None.'''
        res = self.reebill_dict.get('last_recipients', None)
        if res is None:
            self.reebill_dict['last_recipients'] = []
            return self.reebill_dict['last_recipients']
        return res
    
    @last_recipients.setter
    def last_recipients(self, value):
        '''Assigns a list of e-mail addresses representing bill recipients.'''
        self.reebill_dict['last_recipients'] = value
        
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

    def _get_utilbill_for_rs(self, utility, service, rate_structure_name):
        '''Returns the utility bill dictionary with the given utility name and
        rate structure name.'''
        matching_utilbills = [u for u in self._utilbills if u['utility'] ==
                utility and u['service'] == service and
                u['rate_structure_binding'] == rate_structure_name]
        if len(matching_utilbills) == 0:
            raise ValueError(('No utilbill found for utility "%s", rate'
                    'structure "%s"') % (utility, rate_structure_name))
        if len(matching_utilbills) > 1:
            raise ValueError(('Multiple utilbills found for utility "%s", rate'
                    'structure "%s"') % (utility, rate_structure_name))
        return matching_utilbills[0]

    def _set_utilbill_for_id(self, id, new_utilbill_doc):
        '''Used in save_reebill to replace an editable utility bill document
        with a frozen one.'''
        # find all utility bill documents with the given id, and make sure
        # there's exactly 1
        matching_indices = [index for (index, doc) in
                enumerate(self._utilbills) if doc['_id'] == id]
        if len(matching_indices) == 0:
            raise ValueError('No utilbill found for id "%s"' % id)
        if len(matching_indices) > 1:
            raise ValueError('Multiple utilbills found for id "%s"' % id)

        # replace that one with 'new_utilbill_doc'
        self._utilbills[matching_indices[0]] = new_utilbill_doc

    #def hypothetical_total_for_service(self, service_name):
        #'''Returns the total of hypothetical charges for the utilbill whose
        #service is 'service_name'. There's not supposed to be more than one
        #utilbill per service, so an exception is raised if that happens (or if
        #there's no utilbill for that service).'''
        #return self._get_handle_for_service(service_name)['hypothetical_total']

    #def set_hypothetical_total_for_service(self, service_name, new_total):
        #self._get_handle_for_service(service_name)['hypothetical_total'] \
                #= new_total

    #def actual_total_for_service(self, service_name):
        #return self._get_utilbill_for_service(service_name)['total']

    #def set_actual_total_for_service(self, service_name, new_total):
        #self._get_utilbill_for_service(service_name)['total'] = new_total

    def ree_value_for_service(self, service_name):
        '''Returns the total of 'ree_value' (renewable energy value offsetting
        hypothetical charges) for the utilbill whose service is 'service_name'.
        There's not supposed to be more than one utilbill per service.'''
        return self._get_handle_for_service(service_name)['ree_value']

    def set_ree_value_for_service(self, service_name, new_ree_value):
        self._get_handle_for_service(service_name)['ree_value'] = new_ree_value

    def ree_savings_for_service(self, service_name):
        return self._get_handle_for_service(service_name)['ree_savings']

    def set_ree_savings_for_service(self, service_name, new_ree_savings):
        self._get_handle_for_service(service_name)['ree_savings'] = new_ree_savings

    def ree_charges_for_service(self, service_name):
        return self._get_handle_for_service(service_name)['ree_charges']

    def set_ree_charges_for_service(self, service_name, new_ree_charges):
        self._get_handle_for_service(service_name)['ree_charges'] = new_ree_charges

    def hypothetical_chargegroups_for_service(self, service_name):
        '''Returns the list of hypothetical chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service.'''
        return self._get_handle_for_service(service_name)['hypothetical_chargegroups']

    def set_hypothetical_chargegroups_for_service(self, service_name, new_chargegroups):
        '''Set hypothetical chargegroups, based on actual chargegroups.  This is used
        because it is customary to define the actual charges and base the hypothetical
        charges on them.'''
        self._get_handle_for_service(service_name)['hypothetical_chargegroups']\
                = new_chargegroups

    def actual_chargegroups_for_service(self, service_name):
        '''Returns the list of actual chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        return self._get_utilbill_for_service(service_name)['chargegroups']

    def set_actual_chargegroups_for_service(self, service_name, new_chargegroups):
        '''Set hypothetical chargegroups, based on actual chargegroups.  This is used
        because it is customary to define the actual charges and base the hypothetical
        charges on them.'''
        self._get_utilbill_for_service(service_name)['chargegroups'] \
                = new_chargegroups

    def chargegroups_model_for_service(self, service_name):
        '''Returns a shallow list of chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        return self._get_utilbill_for_service(service_name)['chargegroups']\
                .keys()

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

    def utilbill_period_for_service(self, service_name):
        '''Returns start & end dates of the first utilbill found whose service
        is 'service_name'. There's not supposed to be more than one utilbill
        per service.'''
        u = self._get_utilbill_for_service(service_name)
        return u['start'], u['end']

    def set_utilbill_period_for_service(self, service, period):
        '''Changes the period dates of the first utility bill associated with
        this reebill whose service is 'service'.'''
        u = self._get_utilbill_for_service(service)
        u['start'], u['end'] = period

    def renewable_energy_period(self):
        '''Returns 2-tuple of dates (inclusive start, exclusive end) describing
        the period of renewable energy consumption in this bill. In practice,
        this means the read dates of the only meter in the utility bill which
        is equivalent to the utility bill's period.'''
        assert len(self._utilbills) == 1
        return meter_read_period(self._utilbills[0])

    def meter_read_dates_for_service(self, service):
        '''Returns (prior_read_date, present_read_date) of the shadowed meter
        in the first utility bill found whose service is 'service_name'. (There
        should only be one utility bill for the given service, and only one
        register in one meter that has a corresponding shadow register in the
        reebill.)'''
        external_utilbill = self._get_utilbill_for_service(service)
        utilbill_handle = self._get_handle_for_service(service)
        for shadow_register in utilbill_handle['shadow_registers']:
            for meter in external_utilbill['meters']:
                for actual_register in meter['registers']:
                    if actual_register['identifier'] == shadow_register['identifier']:
                        return meter['prior_read_date'], meter['present_read_date']
        raise ValueError(('Utility bill for service "%s" has no meter '
                'containing a register whose identifier matches that of '
                'a shadow register') % service)

    @property
    def utilbill_periods(self):
        '''Return a dictionary whose keys are service and values are the
        utilbill period.'''
        return dict([(service, self.utilbill_period_for_service(service)) for
            service in self.services])

    # TODO: consider calling this meter readings
    def meters_for_service(self, service_name):
        '''Returns a list of copies of meter dictionaries for the utilbill
        whose service is 'service_name'. There's not supposed to be more than
        one utilbill per service, so an exception is raised if that happens (or
        if there's no utilbill for that service).'''
        meters = copy.deepcopy(
                self._get_utilbill_for_service(service_name)['meters'])

        # gather shadow register dictionaries
        shadow_registers = copy.deepcopy(self.shadow_registers(service_name))

        # put shadow: False in all the non-shadow registers, and merge the
        # shadow registers in with shadow: True to replicate the old reebill
        # data structure
        for m in meters:
            for register in m['registers']:
                if 'shadow' in register:
                    continue
                register['shadow'] = False
                for sr in shadow_registers:
                    if sr['identifier'] == register['identifier']:
                        sr['shadow'] = True
                        m['registers'].append(sr)
                        break
        return meters

    def _update_shadow_registers(self):
        '''Refreshes list of "shadow_register" dictionaries in this reebill
        document to match the utility bill documents. This should be called
        whenever _utilbills changes or a register is modified.'''
        # NOTE the fields typically found in a "shadow register" dictionary
        # are: "identifier", "quantity", "quantity_units", 'description", and
        # "register_binding" (a subset of the fields typically found in a
        # register in a utility bill document). the only really necessary
        # fields among these are are "identifier" and "quanity", because their
        # only purpose is represent the quantity a register would have had in a
        # hypothetical situation (and quantity should not be updated because it
        # is the only field in which a shadow register should differ from its
        # corresponding actual register.) however, for consistency, all these
        # fields will continue to be updated--except "quantity", which should
        # not be updated to match)
        for u in self._utilbills:
            handle = self._get_handle_for_service(u['service'])
            for m in u['meters']:
                for r in m['registers']:
                    try:
                        # shadow register dictionary already exists; update its
                        # fields other than "identifier" and "quantity" (though
                        # this is superfluous)
                        shadow_register = next(s for s in
                                handle['shadow_registers'] if s['identifier']
                                == r['identifier'])
                        shadow_register.update({
                            'quantity_units': r['quantity_units'],
                            'description': r['description'],
                            'register_binding': r['register_binding'],
                            'type': r['type'],
                        })
                    except StopIteration:
                        # shadow register dictionary does not exist; create it
                        handle['shadow_registers'].append({
                            'identifier': r['identifier'],
                            'quantity': 0,
                            'quantity_units': r['quantity_units'],
                            'description': r['description'],
                            'register_binding': r['register_binding'],
                            'type': r['type'],
                        })

        # cull any unnecessary shadow registers
        for handle in self.reebill_dict['utilbills']:
            shadow_registers = handle['shadow_registers']
            for shadow_register in shadow_registers:

                # NOTE this loop is an example of prioritizing clarity over
                # efficiency: since there is no "goto", a lot of if statements
                # are required to break out of these loops after a match is
                # found, but who cares about a few extra iterations?
                has_a_match = False
                for u in self._utilbills:
                    for m in u['meters']:
                        if any(r['identifier'] == shadow_register['identifier']
                                for r in m['registers']):
                            has_a_match = True

                if not has_a_match:
                    shadow_registers.remove(shadow_register)

    def set_meter_dates_from_utilbills(self):
        '''Set the meter read dates to the start and end dates of the
        associated utilbill.'''
        for service in self.services:
            for meter in self.meters_for_service(service):
                start, end = self.utilbill_period_for_service(service)
                self.set_meter_read_date(service, meter['identifier'], end, start)

    def set_meter_read_date(self, service, identifier, present_read_date,
            prior_read_date):
        ''' Set the read date for a specified meter.'''
        utilbill = self._get_utilbill_for_service(service)
        meter = next(m for m in utilbill['meters'] if m['identifier'] ==
                identifier)
        meter['present_read_date'] = present_read_date
        meter['prior_read_date'] = prior_read_date

    def set_meter_actual_register(self, service, meter_identifier, register_identifier, quantity):
        ''' Set the total for a specified meter register.'''
        utilbill = self._get_utilbill_for_service(service)
        meter = next(m for m in utilbill['meters'] if m['identifier'] ==
                meter_identifier)
        for register in meter['registers']:
            if register['identifier'] == register_identifier:
                register['quantity'] = quantity

    def set_meter_identifier(self, service, old_identifier, new_identifier):
        if old_identifier == new_identifier:
            return
        utilbill = self._get_utilbill_for_service(service)
        # complain if any existing meter has the same identifier
        for meter in utilbill['meters']:
            if meter['identifier'] == new_identifier:
                raise ValueError("Duplicate Identifier")
        meter = next(m for m in utilbill['meters'] if m['identifier'] ==
                meter_identifier)
        meter['identifier'] = new_identifier

    def set_register_identifier(self, service, old_identifier, new_identifier):
        if old_identifier == new_identifier:
            return
        utilbill = self._get_utilbill_for_service(service)

        # complain if any register in any existing meter has the same
        # identifier
        for meter in utilbill['meters']:
            for register in meter['registers']:
                if register['identifier'] == new_identifier:
                    raise ValueError("Duplicate Identifier")

        # actual register in utilbill
        for meter in utilbill['meters']:
            for register in meter['registers']:
                if register['identifier'] == old_identifier:
                    register['identifier'] = new_identifier

        # hypothetical register in reebill
        for meter in utilbill['meters']:
            for register in meter['registers']:
                if register['identifier'] == old_identifier:
                    register['identifier'] = new_identifier

    def meter_for_register(self, service, identifier):
        meters = self.meters_for_service(service)
        for meter in meters:
            for register in meter['registers']:
                if register['identifier'] == identifier:
                    return meter
    @property
    def meters(self):
        '''Returns a dictionary mapping service names to lists of meters.'''
        return dict([(service, self.meters_for_service(service)) for service
                in self.services])

    def actual_register(self, service, identifier):
        actual_register = [register for register in
                self.actual_registers(service)
                if register['identifier'] == identifier]
        if len(actual_register) == 0:
            return None
        elif len(actual_register) ==1:
            return actual_register[0]
        else:
            raise Exception("More than one actual register named %s"
                    % identifier)

    def actual_registers(self, service):
        '''Returns a list of all nonempty non-shadow register dictionaries of
        all meters for the given service. (The "actual" in the name has nothing
        to do with "actual charges".)
        Registers have rate structure bindings that are used to make the actual
        registers available to rate structure items.'''
        result = []
        for utilbill in self._utilbills:
            for meter in utilbill['meters']:
                result.extend(meter['registers'])
        return result

    def set_actual_register_quantity(self, identifier, quantity):
        '''Sets the value 'quantity' in the first register subdictionary whose
        identifier is 'identifier' to 'quantity'. Raises an exception if no
        register with that identified is found.'''
        for u in self._utilbills:
            for m in u['meters']:
                for r in m['registers']:
                    if r['identifier'] == identifier:
                        r['quantity'] = quantity
                        return

    def all_shadow_registers(self):
        return list(chain.from_iterable([self.shadow_registers(s) for s in
                self.services]))

    def shadow_registers(self, service):
        '''Returns list of copies of shadow register dictionaries for the
        utility bill with the given service.'''
        utilbill_handle = self._get_handle_for_service(service)
        #print repr(utilbill_handle.get('shadow_registers'))
        return copy.deepcopy(utilbill_handle.get('shadow_registers'))

    def set_shadow_register_quantity(self, identifier, quantity):
        '''Sets the value for the key "quantity" in the first shadow register
        found whose identifier is 'identifier' to 'quantity' (assumed to be in
        BTU). Raises an exception if no register with that identifier is
        found.'''
        # find the register and set its quanitity
        for utilbill_handle in self.reebill_dict['utilbills']:
            for register in utilbill_handle['shadow_registers']:
                if register['identifier'] == identifier:
                    # convert units
                    if register['quantity_units'].lower() == 'kwh':
                        # TODO physical constants must be global
                        quantity /= 3412.14
                    elif register['quantity_units'].lower() == 'therms':
                        # TODO physical constants must be global
                        quantity /= 100000.0
                    elif register['quantity_units'].lower() == 'ccf':
                        # TODO 28247371: this is an unfair conversion
                        # TODO physical constants must be global
                        quantity /= 100000.0
                    else:
                        raise ValueError('unknown energy unit %s' %
                                register['quantity_units'])
                    # set the quantity
                    register['quantity'] = quantity
                    return
        raise ValueError('No register found with identifier "%s"' % quantity)

    def utility_name_for_service(self, service_name):
        return self._get_utilbill_for_service(service_name)['utility']

    def rate_structure_name_for_service(self, service_name):
        return self._get_utilbill_for_service(service_name)\
                ['rate_structure_binding']

    @property
    def savings(self):
        '''Value of renewable energy generated, or total savings from
        hypothetical utility bill.'''
        return self.reebill_dict['ree_value']

    def total_renewable_energy(self, ccf_conversion_factor=None):
        '''Returns all renewable energy distributed among shadow registers of
        this reebill, in therms.'''
        # TODO switch to BTU
        if type(ccf_conversion_factor) not in (type(None), float):
            raise ValueError("ccf conversion factor must be a float")
        # TODO: CCF is not an energy unit, and registers actually hold CCF
        # instead of therms. we need to start keeping track of CCF-to-therms
        # conversion factors.
        # https://www.pivotaltracker.com/story/show/22171391
        total_therms = 0
        for register in self.all_shadow_registers():
            quantity = register['quantity']
            unit = register['quantity_units'].lower()
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
                        "https://www.pivotaltracker.com/story/show/28825375")\
                        % (self.account, self.sequence, self.version)
                    # assume conversion factor is 1
                    total_therms += quantity
            else:
                raise ValueError('Unknown energy unit: "%s"' % \
                        register['quantity_units'])
        return total_therms

    #
    # Helper functions
    #

    # the following functions are all about flattening nested chargegroups for the UI grid
    def hypothetical_chargegroups_flattened(self, service,
            chargegroups='hypothetical_chargegroups'):
        utilbill_handle = self._get_handle_for_service(service)
        return flatten_chargegroups_dict(copy.deepcopy(
                utilbill_handle['hypothetical_chargegroups']))

    def set_hypothetical_chargegroups_flattened(self, service, flat_charges):
        utilbill_handle = self._get_handle_for_service(service)
        utilbill_handle['hypothetical_chargegroups'] = \
                unflatten_chargegroups_list(flat_charges)

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

    #def increment_reebill_version(self, session, reebill):
        #'''Converts the reebill into its version successor: increments
        #_id.version, sets issue_date to None, and reloads the utility bills
        #from Mongo (since the reebill is unissued, these will be the current
        #versionless ones, not the ones that belong to the previous old
        #version of this reebill).'''
        #reebill.issue_date = None
        #reebill.version += 1

        ## replace the reebill's utility bill dictionaries with new ones loaded
        ## from mongo. which ones? the un-frozen/editable/"current truth"
        ## versions of the frozen ones currently in the reebill. how do you find
        ## them? i think the only way is by {account, service, utility, start
        ## date, end date}.
        ## TODO reconsider: https://www.pivotaltracker.com/story/show/37521779
        #all_new_utilbills = []
        #for utilbill_handle in reebill.reebill_dict['utilbills']:
            ## load new utility bill
            #old_utilbill = reebill._get_utilbill_for_handle(utilbill_handle)
            #new_utilbill = self.load_utilbill(account=reebill.account,
                    #utility=old_utilbill['utility'],
                    #service=old_utilbill['service'],
                    #start=old_utilbill['start'], end=old_utilbill['end'],
                    ## must not contain "sequence" or "version" keys
                    #sequence=False, version=False)

            ## convert types
            #new_utilbill = deep_map(float_to_decimal, new_utilbill)
            #new_utilbill = convert_datetimes(new_utilbill)

            #all_new_utilbills.append(new_utilbill)

            ## utilbill_handle's _id should match the new utility bill
            #utilbill_handle['id'] = new_utilbill['_id']

        ## replace utilbills with new ones loaded above (all at once)
        #reebill._utilbills = all_new_utilbills


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
            assert utilbill.cprs_document_id == None
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
        elif isinstance(version, date):
            version_dt = date_to_datetime(version)
            docs = self.reebills_collection.find(query, sort=[('_id.version',
                    pymongo.ASCENDING)])
            earliest_issue_date = docs[0]['issue_date']
            if earliest_issue_date is not None and earliest_issue_date < version_dt:
                docs_before_date = [d for d in docs if d['issue_date'] < version_dt]
                mongo_doc = docs_before_date[len(docs_before_date)-1]
            else:
                mongo_doc = docs[docs.count()-1]
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

    def save_reebill(self, reebill, freeze_utilbills=False, force=False):
        '''Saves the MongoReebill 'reebill' into the database. If a document
        with the same account, sequence, and version already exists, the existing
        document is replaced.

        'freeze_utilbills' should be used when issuing a reebill for the first
        time (an original or a correction). This creates "frozen" (immutable)
        copies of the utility bill documents with new _ids and puts the
        reebill's sequence and version in them. This document serves as a
        permanent archive of the utility bill document as it was at the time of
        issuing, and its _id should go in the "document_id" column of the
        "utilbill_reebill" table in MySQL.
        
        Replacing an already-issued reebill (as determined by StateDB) or its
        utility bills is forbidden unless 'force' is True (this should only be
        used for testing).
        
        Returns the _id of the frozen utility bill if 'freeze_utilbills' is
        True, or None otherwise.'''
        # TODO pass session into save_reebill instead of re-creating it
        # https://www.pivotaltracker.com/story/show/36258193
        # TODO 38459029
        # NOTE not using context manager (see comment in load_reebill)
        session = self.state_db.session()
        issued = self.state_db.is_issued(session, reebill.account,
                reebill.sequence, version=reebill.version, nonexistent=False)
        if issued and not force:
            raise IssuedBillError("Can't modify an issued reebill.")
        
        # there will only be a return value if 'freeze_utilbills' is True
        return_value = None

        # NOTE returning the _id of the new frozen utility bill can only work
        # if there is only one utility bill; otherwise some system is needed to
        # specify which _id goes with which utility bill in MySQL
        if len(reebill._utilbills) > 1:
            raise NotImplementedError('Multiple services not yet supported')

        for utilbill_handle in reebill.reebill_dict['utilbills']:
            utilbill_doc = reebill._get_utilbill_for_handle(utilbill_handle)
            if freeze_utilbills:
                # convert the utility bills into frozen copies by putting
                # "sequence" and "version" keys in the utility bill, and
                # changing its _id to a new one
                old_id = utilbill_doc['_id']
                new_id = bson.objectid.ObjectId()

                # copy utility bill doc so changes to it do not persist if
                # saving fails below
                utilbill_doc = copy.deepcopy(utilbill_doc)
                utilbill_doc['_id'] = new_id
                self.save_utilbill(utilbill_doc, force=force,
                        sequence_and_version=(reebill.sequence,
                        reebill.version))
                # saving succeeded: set handle id to match the saved
                # utility bill and replace the old utility bill document with the new one
                utilbill_handle['id'] = new_id
                reebill._set_utilbill_for_id(old_id, utilbill_doc)
                return_value = new_id
            else:
                self.save_utilbill(utilbill_doc, force=force)

        reebill_doc = bson_convert(copy.deepcopy(reebill.reebill_dict))
        self.reebills_collection.save(reebill_doc, safe=True)
        # TODO catch mongo's return value and raise MongoError

        return return_value

    def save_utilbill(self, utilbill_doc, sequence_and_version=None,
            force=False):
        '''Save raw utility bill dictionary. If this utility bill belongs to an
        issued reebill (i.e. has sequence and version in it) it can't be saved.
        force=True overrides this rule; only use it for testing.

        'sequence_and_version' should a (sequence, version) tuple, to be used
        when (and only when) issuing the containing reebill for the first time
        (i.e. calling save_reebill(freeze_utilbills=True). This puts sequence
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

        # check for uniqueness of {account, service, utility, start, end} (and
        # sequence + version if appropriate). Mongo won't enforce this for us.
        unique_fields = {
            'account': utilbill_doc['account'],
            'service': utilbill_doc['service'],
            'utility': utilbill_doc['utility'],
            'start': date_to_datetime(utilbill_doc['start']) if
                    utilbill_doc['start'] is not None else None,
            'end': date_to_datetime(utilbill_doc['end']) if utilbill_doc['end']
                    is not None else None,
        }
        if sequence_and_version is not None:
            # this utility bill is being frozen: check for existing frozen
            # utility bills with same sequence and version (ignoring un-frozen
            # ones)
            unique_fields['sequence'] = sequence_and_version[0]
            unique_fields['version'] = sequence_and_version[1]
        elif 'sequence' in utilbill_doc:
            # NOTE re-saving a frozen utility bill document can only happen when
            # the 'force' argument is used
            assert force is True
            # check for existing frozen utility bills with the same sequence
            # and version (ignoring un-frozen ones)
            unique_fields['sequence'] = utilbill_doc['sequence']
            unique_fields['version'] = utilbill_doc['version']
        else:
            # not frozen: only check for existing utility bills that don't have
            # sequence/version keys
            unique_fields['sequence'] = {'$exists': False}
            unique_fields['version'] = {'$exists': False}
        # NOTE do not use load_utilbills(**unique_fields) here because it
        # unpacks None values into nonexistent keys!
        # see bug #39717171
        for duplicate in self.utilbills_collection.find(unique_fields):
            if duplicate['_id'] != utilbill_doc['_id']:
                raise NotUniqueException(("Can't save utility bill with "
                        "_id=%s: There's already a utility bill with "
                        "id=%s matching %s") % (utilbill_doc['_id'],
                        duplicate['_id'],
                        format_query(unique_fields)))

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

    # TODO remove this method; this should be determined by looking at utility
    # bills in MySQL
    def get_first_issue_date_for_account(self, account):
        '''Returns the issue date of the account's earliest reebill, or None if
        no reebills exist for the customer.'''
        query = {
            '_id.account': account,
            '_id.sequence': 1,
        }
        result = self.reebills_collection.find_one(query)
        if result == None:
            return None
        return MongoReebill(result).issue_date
