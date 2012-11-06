#!/usr/bin/python
import sys
import datetime
from datetime import date, time, datetime
from decimal import Decimal
import pymongo
import bson # part of pymongo package
import functools
from urlparse import urlparse
import httplib
import string
import base64
import itertools as it
import copy
import uuid as UUID
import operator
from billing.util.mongo_utils import bson_convert, python_convert, format_query
from billing.util.dictutils import deep_map, subdict
from billing.util.dateutils import date_to_datetime
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import NoSuchBillException, NotUniqueException, NoRateStructureError, NoUtilityNameError, IssuedBillError, MongoError
from sqlalchemy.orm.exc import NoResultFound

import mongoengine
from mongoengine.base import ValidationError
from mongoengine import Document, EmbeddedDocument
from mongoengine import StringField, IntField, FloatField, BooleanField
from mongoengine import DateTimeField, ListField, DictField
from mongoengine import EmbeddedDocumentField
from mongoengine import ObjectIdField

import pprint
from sqlalchemy.orm.exc import NoResultFound
pp = pprint.PrettyPrinter(indent=1).pprint
sys.stdout = sys.stderr

###############################################################################
# utility functions
###############################################################################

def float_to_decimal(x):
    '''Converts float into Decimal. Used in getter methods.'''
    # str() tells Decimal to automatically figure out how many digts of
    # precision we want
    return Decimal(str(x)) if type(x) is float else x

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

###############################################################################
# utility bill classes
###############################################################################

class Register(EmbeddedDocument):
    '''A register inside a meter in a utility bill document.'''
    quantity_units = StringField(required=True)
    quantity = FloatField(required=True)
    register_binding = StringField(required=True)
    identifier = StringField(required=True)
    type = StringField(required=True)
    description = StringField(required=True)

    def to_dict(self):
        return {field : getattr(self, field) for field in ['quantity_units',
            'quantity', 'register_binding', 'identifier', 'type',
            'description']
        }

    def set_quantity(self, quantity):
        self.quantity = quantity

class Meter(EmbeddedDocument):
    '''A utility meter inside a utility bill document.'''
    registers = ListField(field=EmbeddedDocumentField(Register))
    identifier = StringField(required=True)
    prior_read_date = DateTimeField(required=True)
    present_read_date = DateTimeField(required=True)
    estimated = BooleanField(required=True)

    def to_dict(self):
        result = {
            field : getattr(self, field) for field in [rsi_binding,
                    description, uuid, quantity_units, quantity, rate, total]
        }
        result['registers'] = [r.to_dict() for r in self.registers()]
        return result

    def get_register(self, identifier):
        regs = [r for r in self.regsiters if r.identifier == identifier]
        if len(regs) == 0:
            raise ValueError('No register with identifier "%s"' % identifier)
        if len(regs) > 1:
            raise ValueError('Multiple registers with identifier "%s"' %
                    identifier)
        return regs[0]

    @property
    def read_period(self):
        return self.prior_read_date, self.present_read_date
    def set_read_period(self, prior_read_date, present_read_date):
        self.prior_read_date = prior_read_date
        self.present_read_date = present_read_date

class Charge(EmbeddedDocument):
    '''A charge in a utility bill document.'''
    # in dictionaries some of these fields were absent but now they should all
    # be None when there is no value
    rsi_binding = StringField(required=True)
    description = StringField(required=True)
    uuid = StringField(required=True)
    quantity_units = StringField(required=True)
    quantity = FloatField(required=True)
    rate = FloatField(required=True)
    total = FloatField(required=True)

    def to_dict():
        return {name : getattr(self, name) for name in [rsi_binding,
                description, uuid, quantity_units, quantity, rate, total]}

class UtilBill(Document):
    '''Schema definition for utility bill document in Mongo.'''
    meta = {
        # "db_alias" tells MongoEngine which database this goes with, while
        # still allowing it to be configurable.
        'db_alias': 'utilbills',
        'collection': 'utilbills',
        'allow_inheritance': False
    }

    _id = ObjectIdField(required=True)

    # unofficially unique identifying fields
    account = StringField(required=True)
    utility = StringField(required=True)
    service = StringField(required=True)
    start = DateTimeField(required=True) # Mongo does not have plain dates
    end = DateTimeField(required=True)

    # other fields
    chargegroups = DictField(required=True,
            field=ListField(field=EmbeddedDocumentField(Charge)))
    total = FloatField(required=True)
    rate_structure_binding = StringField(required=True)
    service_address = DictField(required=True, field=StringField())
    billing_address = DictField(required=True, field=StringField())
    meters = ListField(field=EmbeddedDocumentField(Meter), required=True)

    @property
    def period(self):
        return self.start, self.end

    @property
    def read_period(self):
        if len(self.meters) != 1:
            raise ValueError("There must be exactly one meter")
        m = meters[0]
        return m.prior_read_date, m.present_read_date

    def get_meter(self, identifier):
        '''Returns the Meter with the given identifier.'''
        meters = [m for m in self.meters if m.identifier == identifier]
        if len(meters) == 0:
            raise ValueError('No meter with identifier "%s"' % identifier)
        if len(meters) > 1:
            raise ValueError('Multiple meters with identifier "%s"' %
                    identifier)
        return meters[0]

###############################################################################
# reebill
###############################################################################

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
    def __init__(self, reebill_data, utilbills):
        assert isinstance(reebill_data, dict)
        # defensively copy whatever is passed in; who knows where the caller got it from
        self.reebill_dict = copy.deepcopy(reebill_data)
        self._utilbills = copy.deepcopy(utilbills)

    def clear(self):
        '''Code for clearing out fields of newly-rolled rebill (moved from
        __init__, called by Process.roll_bill). TODO remove this.'''
        # set start date of each utility bill in this reebill to the end date
        # of the previous utility bill for that service
        for service in self.services:
            prev_start, prev_end = self.utilbill_period_for_service(service)
            self.set_utilbill_period_for_service(service, (prev_end, None))

        # process rebill
        self.period_begin = self.period_end
        self.period_end = None
        self.total_adjustment = Decimal("0.00")
        self.hypothetical_total = Decimal("0.00")
        self.actual_total = Decimal("0.00")
        self.ree_value = Decimal("0.00")
        self.ree_charges = Decimal("0.00")
        self.ree_savings = Decimal("0.00")
        self.due_date = None
        self.issue_date = None
        self.motd = None

        # this should always be set from the value in MySQL, which holds the
        # "current" discount rate for each customer
        self.discount_rate = Decimal("0.00")

        self.prior_balance = Decimal("0.00")
        self.total_due = Decimal("0.00")
        self.balance_due = Decimal("0.00")
        self.payment_received = Decimal("0.00")
        self.balance_forward = Decimal("0.00")

        for service in self.services:
            # get utilbill numbers and zero them out
            self.set_actual_total_for_service(service, Decimal("0.00")) 
            self.set_hypothetical_total_for_service(service, Decimal("0.00")) 
            self.set_ree_value_for_service(service, Decimal("0.00")) 
            self.set_ree_savings_for_service(service, Decimal("0.00")) 
            self.set_ree_charges_for_service(service, Decimal("0.00")) 

            # set new UUID's & clear out the last bound charges
            actual_chargegroups = self.actual_chargegroups_for_service(service)
            for group, charges in actual_chargegroups.items():
                for charge in charges:
                    charge.uuid = str(UUID.uuid1())
                    charge.rate = None
                    charge.quantity = None
                    charge.total = None
                    
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
                utilbill = self.get_utilbill_for_service(service)
                for meter in utilbill.meters:
                    meter.prior_read_date = meter.present_read_date
                    meter.prior_read_date = None
                    for register in meter.registers:
                        register.quantity = Decimal(0.0)
                for shadow_register in self.shadow_registers(service):
                    self.set_shadow_register_quantity(shadow_register.identifier,
                            Decimal(0.0))

            # zero out statistics section
            self.reebill_dict['statistics'] = {
                "conventional_consumed": 0,
                "renewable_consumed": 0,
                "renewable_utilization": 0,
                "conventional_utilization": 0,
                "renewable_produced": 0,
                "co2_offset": 0,
                "total_savings": Decimal("0.00"),
                "total_renewable_consumed": 0,
                "total_renewable_produced": 0,
                "total_trees": 0,
                "total_co2_offset": 0,
                "consumption_trend": [],
            }

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
        for u in self._utilbills:
            u['account'] = account
            if 'sequence' in u:
                del u['sequence']
            if 'version' in u:
                del u['version']

    def new_utilbill_ids(self):
        '''Replaces _ids in utility bill documents and the reebill document's
        references to them, and removed "sequence" and "version" keys if
        present (to convert frozen utility bill into editable one). Used when
        rolling to create copies of the utility bills.'''
        for utilbill_handle in self.reebill_dict['utilbills']:
            utilbill_doc = self._get_utilbill_for_handle(utilbill_handle)
            new_id = bson.objectid.ObjectId()
            utilbill_handle['id'] = utilbill_doc['_id'] = new_id
            if 'sequence' in utilbill_doc:
                del utilbill_doc['sequence']
            if 'version' in utilbill_doc:
                del utilbill_doc['version']

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

    # TODO these must die
    @property
    def period_begin(self):
        return python_convert(self.reebill_dict['period_begin'])
    @period_begin.setter
    def period_begin(self, value):
        self.reebill_dict['period_begin'] = value
    @property
    def period_end(self):
        return python_convert(self.reebill_dict['period_end'])
    @period_end.setter
    def period_end(self, value):
        self.reebill_dict['period_end'] = value
    
    @property
    def discount_rate(self):
        '''Discount rate is a Decimal.'''
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
        issued, including unpaid charges from previous bills. Returns a
        Decimal.'''
        return self.reebill_dict['balance_due']
    @balance_due.setter
    def balance_due(self, value):
        self.reebill_dict['balance_due'] = value

    @property
    def late_charge_rate(self):
        '''Late charges rate is a Decimal.'''
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
        if type(value) is not Decimal: raise ValueError("Requires Decimal")
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

    @property
    def statistics(self):
        '''Returns a dictionary of the information that goes in the
        "statistics" section of reebill.'''
        return self.reebill_dict['statistics']
    @statistics.setter
    def statistics(self, value):
        self.reebill_dict['statistics'].update(value)

    # TODO this must die https://www.pivotaltracker.com/story/show/36492387
    @property
    def actual_total(self):
        return self.reebill_dict['actual_total']
    @actual_total.setter
    def actual_total(self, value):
        self.reebill_dict['actual_total'] = value

    @property
    def hypothetical_total(self):
        return self.reebill_dict['hypothetical_total']
    @hypothetical_total.setter
    def hypothetical_total(self, value):
        self.reebill_dict['hypothetical_total'] = value

    @property
    def ree_value(self):
        return self.reebill_dict['ree_value']
    @ree_value.setter
    def ree_value(self, value):
        self.reebill_dict['ree_value'] = value

    def _utilbill_ids(self):
        '''Useful for debugging.'''
        # note order is not guranteed so the result may look weird
        return zip([h['id'] for h in self.reebill_dict['utilbills']],
                [u._id for u in self._utilbills])

    def _get_utilbill_for_service(self, service):
        '''Returns utility bill document having the given service. There must
        be exactly one.'''
        matching_utilbills = [u for u in self._utilbills if u.service ==
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
                u._id]
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
        matching_utilbills = [u for u in self._utilbills if u._id == id]
        if len(matching_utilbills) < 0:
            raise ValueError('No utilbill found for id "%s"' % id)
        if len(matching_utilbills) > 1:
            raise ValueError('Multiple utilbills found for id "%s"' % id)
        return matching_utilbills[0]

    def _set_utilbill_for_id(self, id, new_utilbill_doc):
        '''Used in save_reebill to replace an editable utility bill document
        with a frozen one.'''
        # find all utility bill documents with the given id, and make sure
        # there's exactly 1
        matching_indices = [index for (index, doc) in
                enumerate(self._utilbills) if doc._id == id]
        if len(matching_indices) < 0:
            raise ValueError('No utilbill found for id "%s"' % id)
        if len(matching_indices) > 1:
            raise ValueError('Multiple utilbills found for id "%s"' % id)

        # replace that one with 'new_utilbill_doc'
        self._utilbills[matching_indices[0]] = new_utilbill_doc

    def hypothetical_total_for_service(self, service_name):
        '''Returns the total of hypothetical charges for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        return self._get_handle_for_service(service_name)['hypothetical_total']

    def set_hypothetical_total_for_service(self, service_name, new_total):
        self._get_handle_for_service(service_name)['hypothetical_total'] \
                = new_total

    def actual_total_for_service(self, service_name):
        return self._get_utilbill_for_service(service_name)['total']

    def set_actual_total_for_service(self, service_name, new_total):
        self._get_utilbill_for_service(service_name)['total'] = new_total

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

    # TODO 37477445 better to remove than make work with UtilBill class
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
        return self._get_utilbill_for_service(service_name).chargegroups

    # TODO 37477445 better to remove than make work with UtilBill class
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
        return self._get_utilbill_for_service(service_name).chargegroups.keys()

    @property
    def services(self):
        '''Returns a list of all services for which there are utilbills.'''
        return [u.service for u in self._utilbills]

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
        print self.services
        service = service.lower()
        if service not in [s.lower() for s in self.services]:
            raise ValueError('Unknown service %s: services are %s' % (service, self.services))

        if 'suspended_services' not in self.reebill_dict:
            self.reebill_dict['suspended_services'] = []
        if service not in self.reebill_dict['suspended_services']:
            self.reebill_dict['suspended_services'].append(service)
        print '%s-%s suspended_services set to %s' % (self.account, self.sequence, self.reebill_dict['suspended_services'])

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
        u = self._get_utilbill_for_service(service_name).period

    def set_utilbill_period_for_service(self, service, period):
        '''Changes the period dates of the first utility bill associated with
        this reebill whose service is 'service'.'''
        u = self._get_utilbill_for_service(service)
        u.start, u.end = period

    def meter_read_period(self, service):
        '''Returns tuple of period dates for first meter found with the given
        service.'''
        return self._get_utilbill_for_service(service).meter_period

    def meter_read_dates_for_service(self, service):
        '''Returns (prior_read_date, present_read_date) of the shadowed meter
        in the first utility bill found whose service is 'service_name'. (There
        should only be one utility bill for the given service, and only one
        register in one meter that has a corresponding shadow register in the
        reebill.)'''
        external_utilbill = self._get_utilbill_for_service(service)
        utilbill_handle = self._get_handle_for_service(service)
        for shadow_register in utilbill_handle['shadow_registers']:
            for meter in external_utilbill.meters:
                for actual_register in meter.registers:
                    if actual_register.identifier == shadow_register['identifier']:
                        return meter.prior_read_date, meter.present_read_date
        raise Exception(('Utility bill for service "%s" has no meter '
                'containing a register whose identifier matches that of '
                'a shadow register') % service)

    @property
    def utilbill_periods(self):
        '''Return a dictionary whose keys are service and values are the
        utilbill period.'''
        return dict([(service, self.utilbill_period_for_service(service)) for
            service in self.services])

    # TODO 37477445 remove this
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

    # TODO 37477445 replace with utility bill meter; remove this method from MongoReebill
    def meter(self, service, identifier):
        return self._get_utilbill_for_service(service).get_meter(identifier).to_dict()

    # TODO 37477445 replace with utility bill meter; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
    def delete_meter(self, service, identifier):
        '''Deletes all meters the utility bill for the given service.'''
        ub = self._get_utilbill_for_service(service)
        for ub in self._utilbills:
            if ub['service'] == service:
                for meter in ub['meters']:
                    del meter

    # TODO 37477445 replace with utility bill method; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
    def new_meter(self, service):
        new_meter = Meter(
            identifier=str(UUID.uuid4()),
            prior_read_date=datetime.now(),
            present_read_date=None,
            estimated=False,
            resgisters=[],
        )
        self.get_utilbill_for_service(service).meters.append(new_meter)
        return new_meter

    # TODO 37477445 replace with utility bill method; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
    def new_register(self, service, meter_identifier):
        identifier = str(UUID.uuid4())
        new_actual_register = Register(
            description="No description",
            quantity=0,
            quantity_units= "No units",
            shadow=False,
            indentifier=identifier,
            type=total,
            register_binding="No binding",
        )
        new_shadow_register = {
            "description" : "No description",
            "quantity" : 0,
            "quantity_units" : "No Units",
            "shadow" : True,
            "identifier" : identifier,
            "type" : "total",
            "register_binding": "No Binding"
        }

        # put actual register in meter in utilbill document
        utilbill = self._get_utilbill_for_service(service)
        meter = utilbill.get_meter(meter_identifier)
        meter.registers.append(new_shadow_register)

        # put hypothetical register in 'utilbills' list of reebill document
        self._get_handle_for_service(service)['shadow_registers']\
                .append(new_shadow_register)
        return (new_actual_register.to_dict(), new_shadow_register)

    # TODO 37477445 repl_ace with utility bill method; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
    def set_meter_identifier(self, service, old_identifier, new_identifier):
        self._get_utilbill_for_service(service).get_meter(old_identifier)\
                .identifier = new_identifier

    # TODO 37477445 replace with utility bill method; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
    def set_register_identifier(self, service, old_identifier, new_identifier):
        if old_identifier == new_identifier:
            return
        utilbill = self._get_utilbill_for_service(service)

        # complain if any register in any existing meter has the same
        # identifier
        for meter in utilbill.meters:
            for register in meter.registers:
                if register.identifier == new_identifier:
                    raise Exception("Duplicate Identifier")

        # actual register in utilbill
        for meter in utilbill['meters']:
            for register in meter.registers:
                if register['identifier'] == old_identifier:
                    register['identifier'] = new_identifier

        # hypothetical register in reebill
        for meter in utilbill['meters']:
            for register in meter['registers']:
                if register['identifier'] == old_identifier:
                    register['identifier'] = new_identifier

    # TODO delete or move to meter
    # (part of "reebill structure editor": may be dead)
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

    # TODO 37477445 replace with utility bill method; remove this method from MongoReebill
    # (part of "reebill structure editor": may be dead)
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

    # TODO 37477445 replace with utility bill method; remove this method from MongoReebill
    def actual_registers(self, service):
        '''Returns a list of all nonempty non-shadow register dictionaries of
        all meters for the given service. (The "actual" in the name has nothing
        to do with "actual charges".)
        Registers have rate structure bindings that are used to make the actual
        registers available to rate structure items.'''
        result = []
        for utilbill in self._utilbills:
            for meter in utilbill.meters:
                result.extend([r.to_dict() for r in meter.registers])
        return result

    def shadow_registers(self, service):
        '''Returns list of copies of shadow register dictionaries for the
        utility bill with the given service.'''
        utilbill_handle = self._get_handle_for_service(service)
        return copy.deepcopy(utilbill_handle['shadow_registers'])

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
                        quantity /= Decimal('3412.14')
                    elif register['quantity_units'].lower() == 'therms':
                        # TODO physical constants must be global
                        quantity /= Decimal('100000.0')
                    elif register['quantity_units'].lower() == 'ccf':
                        # TODO 28247371: this is an unfair conversion
                        # TODO physical constants must be global
                        quantity /= Decimal('100000.0')
                    else:
                        raise Exception('unknown energy unit %s' %
                                register['quantity_units'])
                    # set the quantity
                    register['quantity'] = quantity
                    return
        raise Exception('No register found with identifier "%s"' % quantity)

    # TODO move to utility bill (eventually)
    def utility_name_for_service(self, service_name):
        return self._get_utilbill_for_service(service_name).utility

    # TODO move to utility bill (eventually)
    def rate_structure_name_for_service(self, service_name):
        return self._get_utilbill_for_service(service_name)\
                .rate_structure_binding

    @property
    def savings(self):
        '''Value of renewable energy generated, or total savings from
        hypothetical utility bill.'''
        return self.reebill_dict['ree_value']

    def total_renewable_energy(self, ccf_conversion_factor=None):
        '''Returns all renewable energy distributed among shadow registers of
        this reebill, in therms.'''
        # TODO switch to BTU
        if type(ccf_conversion_factor) not in (type(None), Decimal):
            raise ValueError("ccf conversion factor must be a Decimal")
        # TODO: CCF is not an energy unit, and registers actually hold CCF
        # instead of therms. we need to start keeping track of CCF-to-therms
        # conversion factors.
        # https://www.pivotaltracker.com/story/show/22171391
        total_therms = Decimal(0)
        for utilbill_handle in self.reebill_dict['utilbills']:
            for register in u['actual_registers']:
                quantity = register['quantity']
                unit = register['quantity_units'].lower()
                if unit == 'therms':
                    total_therms += quantity
                elif unit == 'btu':
                    # TODO physical constants must be global
                    total_therms += quantity / Decimal("100000.0")
                elif unit == 'kwh':
                    # TODO physical constants must be global
                    total_therms += quantity / Decimal(".0341214163")
                elif unit == 'ccf':
                    if ccf_conversion_factor is not None:
                        total_therms += quantity * ccf_conversion_factor
                    else:
                        # TODO: 28825375 - need the conversion factor for this
                        raise Exception(("Register contains gas measured "
                            "in ccf: can't convert that into energy "
                            "without the multiplier."))
                else:
                    raise Exception('Unknown energy unit: "%s"' % \
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

    def actual_chargegroups_flattened(self, service):
        utilbill = self._get_utilbill_for_service(service)
        return flatten_chargegroups_dict(copy.deepcopy(
                utilbill.chargegroups))


    # TODO 37477445 remove
    def set_hypothetical_chargegroups_flattened(self, service, flat_charges):
        utilbill_handle = self._get_handle_for_service(service)
        utilbill_handle['hypothetical_chargegroups'] = \
                unflatten_chargegroups_list(flat_charges)

    # TODO 37477445 remove
    def set_actual_chargegroups_flattened(self, service, flat_charges):
        utilbill = self._get_utilbill_for_service(service)
        utilbill['chargegroups'] = unflatten_chargegroups_list(flat_charges)



###############################################################################
# DAO
###############################################################################

class ReebillDAO:
    '''A "data access object" for reading and writing reebills in MongoDB.'''

    def __init__(self, state_db, host='localhost', port=27017,
            database=None, **kwargs):
        self.state_db = state_db

        try:
            self.connection = pymongo.Connection(host, int(port)) 
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        finally:
            # TODO disconnect from the database __del__
            pass
        
        self.reebills_collection = self.connection[database]['reebills']
        self.utilbills_collection = self.connection[database]['utilbills']

    def _get_version_query(self, account, sequence, specifier):
        '''Returns the version part of a Mongo query for a reebill based on the
        "version specifier": .'''

        # TODO
        if isinstance(specifier, date):
            raise NotImplementedError

        raise ValueError('Unknown version specifier "%s"' % specifier)

    def increment_reebill_version(self, session, reebill):
        '''Converts the reebill into its version successor: increments
        _id.version, sets issue_date to None, and reloads the utility bills
        from Mongo (since the reebill is unissued, these will be the current
        versionless ones, not the ones that belong to the previous old
        version of this reebill).'''
        reebill.issue_date = None
        reebill.version += 1

        # replace the reebill's utility bill dictionaries with new ones loaded
        # from mongo. which ones? the un-frozen/editable/"current truth"
        # versions of the frozen ones currently in the reebill. how do you find
        # them? i think the only way is by {account, service, utility, start
        # date, end date}.
        # TODO reconsider: https://www.pivotaltracker.com/story/show/37521779
        all_new_utilbills = []
        for utilbill_handle in reebill.reebill_dict['utilbills']:
            # load new utility bill
            old_utilbill = reebill._get_utilbill_for_handle(utilbill_handle)
            new_utilbill = self.load_utilbill(account=reebill.account,
                    utility=old_utilbill['utility'],
                    service=old_utilbill['service'],
                    start=old_utilbill['start'], end=old_utilbill['end'],
                    # must not contain "sequence" or "version" keys
                    sequence=False, version=False)

            all_new_utilbills.append(new_utilbill)

            # utilbill_handle's _id should match the new utility bill
            utilbill_handle['id'] = new_utilbill._id

        # replace utilbills with new ones loaded above (all at once)
        reebill._utilbills = all_new_utilbills


    def load_utilbills(self, account=None, service=None, utility=None,
            start=None, end=None, sequence=None, version=None):
        '''Loads 0 or more utility bill documents from Mongo, returns a list of
        the raw dictionaries ordered by start date.'''
        query = {}
        if account is not None:
            query.update({'account': account})
        if utility is not None:
            query.update({'utility': utility})
        if service is not None:
            query.update({'service': service})
        if start is not None:
            query.update({'start': date_to_datetime(start)})
        if end is not None:
            query.update({'end': date_to_datetime(end)})
        if sequence is not None:
            query.update({'sequence': sequence})
        if version is not None:
            query.update({'version': version})
        return list(UtilBill.objects(__raw__=query).all())

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

        # MongoEngine get() ensures uniqueness ("raw" means query like regular
        # pymongo)
        docs = UtilBill.objects(__raw__=query)

    def _load_all_utillbills_for_reebill(self, session, reebill_doc):
        '''Loads all utility bill documents from Mongo that match the ones in
        the 'utilbills' list in the given reebill dictionary (NOT MongoReebill
        object). Returns list of dictionaries with converted types.'''
        result = []
        for utilbill_handle in reebill_doc['utilbills']:
            result.append(UtilBill.objects().get(_id=utilbill_handle['id']))
        return result

    def load_reebill(self, account, sequence, version='max'):
        '''Returns the reebill with the given account and sequence, and the a
        version: a specific version number, an issue date (before which the
        greatest issued version is returned, and after which the greatest
        overall version is returned), or 'max', which specifies the greatest
        version overall.'''
        with DBSession(self.state_db) as session:
            # TODO looks like somebody's temporary hack should be removed
            if account is None: return None
            if sequence is None: return None

            query = {
                "_id.account": str(account),
                # TODO stop passing in sequnce as a string from BillToolBridge
                "_id.sequence": int(sequence),
            }

            # TODO figure out how to move this into _get_version_query(): it can't
            # be expressed as part of the query, except maybe with a javascript
            # "where" clause
            if isinstance(version, int):
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
                raise ValueError('Unknown version specifier "%s"' % version)

            if mongo_doc is None:
                raise NoSuchBillException(("no reebill found in %s: query was %s")
                        % (self.reebills_collection, format_query(query)))

            # convert types in reebill document
            mongo_doc = deep_map(float_to_decimal, mongo_doc)
            mongo_doc = convert_datetimes(mongo_doc) # this must be an assignment because it copies

            # load utility bills
            utilbill_docs = self._load_all_utillbills_for_reebill(session, mongo_doc)

            mongo_reebill = MongoReebill(mongo_doc, utilbill_docs)
            return mongo_reebill

    def load_reebills_for(self, account, version='max'):
        if not account: return None
        with DBSession(self.state_db) as session:
            sequences = self.state_db.listSequences(session, account)
        return [self.load_reebill(account, sequence) for sequence in sequences]
    
    def load_reebills_in_period(self, account, version=0, start_date=None,
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
            query = { '_id.account': str(account) }
            if isinstance(version, int):
                query.update({'_id.version': version})
            elif version == 'any':
                pass
            # TODO max version
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
                mongo_doc = deep_map(float_to_decimal, mongo_doc)
                utilbill_docs = self._load_all_utillbills_for_reebill(session, mongo_doc)
                result.append(MongoReebill(mongo_doc, utilbill_docs))
            return result

    def last_issue_date(self, session, account):
        last_sequence = self.state_db.last_issued_sequence(session, account)
        reebill = self.load_reebill(account, last_sequence)
        return reebill.issue_date

        
    def save_reebill(self, reebill, freeze_utilbills=False, force=False):
        '''Saves the MongoReebill 'reebill' into the database. If a document
        with the same account, sequence, and version already exists, the existing
        document is replaced.

        'freeze_utilbills' should be used when issuing a reebill for the first
        time (an original or a correction). This creates immutable copies of
        the utility bill documents with new _ids and puts the reebill's
        sequence and version in them.
        
        Replacing an already-issued reebill (as determined by StateDB, using
        the rule that all versions except the highest are issued) or its
        utility bills is forbidden unless 'force' is True (this should only be
        used for testing).'''
        # TODO pass session into save_reebill instead of re-creating it
        # https://www.pivotaltracker.com/story/show/36258193
        # TODO 38459029
        with DBSession(self.state_db) as session:
            issued = self.state_db.is_issued(session, reebill.account,
                    reebill.sequence, version=reebill.version, nonexistent=False)
            attached = self.state_db.is_attached(session, reebill.account,
                    reebill.sequence, nonexistent=False)
            if issued and not force:
                raise IssuedBillError("Can't modify an issued reebill.")
            if (issued or attached) and freeze_utilbills:
                raise IssuedBillError("Can't freeze utility bills because this "
                        "reebill is attached or issued; frozen utility bills "
                        "should already exist")
            
            for utilbill_handle in reebill.reebill_dict['utilbills']:
                utilbill_doc = reebill._get_utilbill_for_handle(utilbill_handle)
                if freeze_utilbills:
                    # this reebill is being attached (usually right before
                    # issuing): convert the utility bills into frozen copies by
                    # putting "sequence" and "version" keys in the utility
                    # bill, and changing its _id to a new one
                    old_id = utilbill_doc._id
                    new_id = bson.objectid.ObjectId()

                    # copy utility bill doc so changes to it do not persist if
                    # saving fails below
                    utilbill_doc = copy.deepcopy(utilbill_doc)
                    utilbill_doc._id = new_id
                    self._save_utilbill(utilbill_doc, force=force,
                            sequence_and_version=(reebill.sequence,
                            reebill.version))
                    # saving succeeded: set handle id to match the saved
                    # utility bill and replace the old utility bill document with the new one
                    utilbill_handle['id'] = new_id
                    reebill._set_utilbill_for_id(old_id, utilbill_doc)
                else:
                    self._save_utilbill(utilbill_doc, force=force)

            reebill_doc = bson_convert(copy.deepcopy(reebill.reebill_dict))
            self.reebills_collection.save(reebill_doc, safe=True)
            # TODO catch mongo's return value and raise MongoError

    def _save_utilbill(self, utilbill_doc, sequence_and_version=None,
            force=False):
        '''Save raw utility bill dictionary. If this utility bill belongs to an
        issued reebill (i.e. has sequence and version in it) it can't be saved.
        force=True overrides this rule; only use it for testing.

        'sequence_and_version' should a (sequence, version) tuple, to be used
        when (and only when) issuing the containing reebill for the first time
        (i.e. calling save_reebill(freeze_utilbills=True). This puts sequence
        and version keys into the utility bill. (If those keys are already in
        the utility bill, you won't be able to save it.)'''

        # check for uniqueness of {account, service, utility, start, end} (and
        # sequence + version if appropriate). Mongo won't enforce this for us.
        unique_fields = {
            'account': utilbill_doc.account,
            'service': utilbill_doc.service,
            'utility': utilbill_doc.utility,
            'start': utilbill_doc.start,
            'end': utilbill_doc.end,
        }
        if sequence_and_version is not None:
            # this utility bill is being frozen: check for existing frozen
            # utility bills with same sequence and version (ignoring un-frozen
            # ones)
            unique_fields['sequence'] = sequence_and_version[0]
            unique_fields['version'] = sequence_and_version[1]
        elif 'sequence' in utilbill_doc:
            # this utility bill is already a frozen one and has been saved:
            # check for existing frozen utility bills with the same sequence
            # and version (ignoring un-frozen ones)
            unique_fields['sequence'] = utilbill_doc.sequence
            unique_fields['version'] = utilbill_doc.version
        else:
            # not frozen: only check for existing utility bills that don't have
            # sequence/version keys
            unique_fields['sequence'] = {'$exists': False}
            unique_fields['version'] = {'$exists': False}
        for duplicate in self.load_utilbills(**unique_fields):
            if duplicate._id != utilbill_doc._id:
                raise NotUniqueException(("Can't save utility bill with "
                        "_id=%s: There's already a utility bill with "
                        "_id=%s matching %s") % (utilbill_doc._id,
                        duplicate._id, format_query(unique_fields)))

        if sequence_and_version is not None:
            utilbill_doc.sequence = sequence_and_version[0]
            utilbill_doc.version = sequence_and_version[1]
            # force creation of a new document (because the _id has just been
            # changed in save_reebill())
            utilbill_doc.save(safe=True, force_insert=True)
        else:
            # normal save
            utilbill_doc.save(safe=True)

    def delete_reebill(self, account, sequence, version):
        # load reebill in order to find utility bills
        reebill = self.load_reebill(account, sequence, version)

        # first ensure that each utility bill can be found and the reebill can
        # be found (to help keep this operation atomic)
        for u in reebill._utilbills:
            UtilBill.objects().get(_id=u._id)
        self.reebills_collection.find({
            '_id.account': account,
            '_id.sequence': sequence,
            '_id.version': version,
        })

        # remove each utility bill, then the reebill
        for u in reebill._utilbills:
            # if this is a frozen utility bill, delete it
            if 'sequence' in u:
                u.delete(safe=True)

            # if this is an editable utility bill, delete it only if the
            # reebill's version is 0. (the editable document is retained for
            # version > 0 so new versions can still be created after this
            # version is removed.) this also deletes the "editable version of"
            # the frozen utility bill above, if any.
            #
            # (NOTE it is not actually possible to identify the "editable
            # version of" a given frozen utility bill because the keys can
            # change; see
            # https://www.pivotaltracker.com/projects/397621#!/stories/37521779)
            if version == 0:
                q = {
                    'account': account,
                    'service': u['service'],
                    'utility': u['utility'],
                    'start': None if u['start'] is None
                            else date_to_datetime(u['start']),
                    'end': None if u['end'] is None
                            else date_to_datetime(u['end']),
                    'sequence': {'$exists': False},
                    'version': {'$exists': False},
                }
                UtilBill.objects().find(__raw__=q).remove(safe=True)

        result = self.reebills_collection.remove({
            '_id.account': account,
            '_id.sequence': sequence,
            '_id.version': version,
        }, safe=True)
        if result['err'] is not None or result['n'] == 0:
            raise MongoError(result)

    def get_first_bill_date_for_account(self, account):
        '''Returns the start date of the account's earliest reebill, or None if
        no reebills exist for the customer.'''
        query = {
            '_id.account': account,
            '_id.sequence': 1,
        }
        result = self.reebills_collection.find_one(query)
        if result == None:
            raise NoSuchBillException('First reebill for account %s is missing'
                    % account)
        # empty utilbills list because it doesn't matter
        return MongoReebill(result, []).period_begin

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

    def last_sequence(self, account):
        '''Returns the sequence of the last reebill for the given account, or 0
        if no reebills were found. This is different from
        StateDB.last_sequence() because it uses Mongo; there may be un-issued
        reebills in Mongo that are not in MySQL.'''
        result = self.reebills_collection.find_one({
            '_id.account': account
            }, sort=[('sequence', pymongo.DESCENDING)])
        if result == None:
            return 0
        return MongoReebill(result).sequence

