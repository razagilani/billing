#!/usr/bin/python
import sys
import datetime
from datetime import date, time, datetime
from decimal import Decimal
import pymongo
import functools
from urlparse import urlparse
import httplib
import string
import base64
import itertools as it
import copy
import uuid as UUID
from billing.mongo_utils import bson_convert, python_convert
from billing.dictutils import deep_map
from billing.dateutils import date_to_datetime
from billing.session_contextmanager import DBSession
import pprint
pp = pprint.PrettyPrinter(indent=1)
sys.stdout = sys.stderr


# type-conversion functions

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
        return [convert_datetimes(element, datetime_keys, ancestor_key) for element in x]
    return x


def check_issued(method):
    '''Decorator to evaluate the issued state.'''
    @functools.wraps(method)
    def wrapper(instance, *args, **kwargs):
        if 'issue_date' in instance.reebill_dict and instance.reebill_dict['issue_date'] is not None:
            raise Exception("ReeBill cannot be modified once isssued.")
        return method(instance, *args, **kwargs)
    return wrapper

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

    def __init__(self, reebill_data):

        # the bill is being instantiated from Mongo 
        if type(reebill_data) is dict:
            self.reebill_dict = reebill_data
            return

        # the bill is being instantiated from an existing instance
        elif type(reebill_data) is MongoReebill:

            reebill = reebill_data

            # copy the dict passed because we set it here as instance data and start
            # operating on that data. This destroys the reebill from whence it came
            self.reebill_dict = copy.copy(reebill.reebill_dict)

            # increment sequence
            self.sequence = reebill.sequence + 1

            # set start date of each utility bill in this reebill to the end date
            # of the previous utility bill for that service
            for service in reebill.services:
                prev_start, prev_end = reebill.utilbill_period_for_service(service)
                self.set_utilbill_period_for_service(service, (prev_end, None))

            # process rebill
            self.period_begin = reebill.period_end
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
                        self.set_actual_register_quantity(actual_register['identifier'], 0.0)
                    for shadow_register in self.shadow_registers(service):
                        self.set_shadow_register_quantity(shadow_register['identifier'], 0.0)


                # zero out statistics section
                statistics = self.statistics

                statistics["conventional_consumed"] = 0
                statistics["renewable_consumed"] = 0
                statistics["renewable_utilization"] = 0
                statistics["conventional_utilization"] = 0
                statistics["renewable_produced"] = 0
                statistics["co2_offset"] = 0
                statistics["total_savings"] = Decimal("0.00")
                statistics["total_renewable_consumed"] = 0
                statistics["total_renewable_produced"] = 0
                statistics["total_trees"] = 0
                statistics["total_co2_offset"] = 0
                statistics["consumption_trend"] = []

                self.statistics = statistics

        # return a new empty instance
        elif type(reebill_data) is None:


            self.reebill_dict = {}

            # initialize the reebill_dict through the MongoReeBill interface
            self.account = ""
            self.sequence = 0 
            self.branch = 0 
            self.issue_date = None
            self.due_date = None
            self.period_begin = None
            self.period_end = None
            self.balance_due = Decimal("0.00") 
            self.prior_balance = Decimal("0.00") 
            self.payment_received = Decimal("0.00")

            # consider a reset addr function
            self.billing_address = {"ba_addressee": None, "ba_street1": None, "ba_city": None, "ba_state": None, "ba_postalcode": None}
            self.service_address = {"sa_addressee": None, "sa_street1": None, "sa_city": None, "sa_state": None, "sa_postalcode": None}
            self.ree_charges = Decimal("0.00")
            self.ree_savings = Decimal("0.00")
            self.total_adjustment = Decimal("0.00")
            self.balance_forward = Decimal("0.00")
            self.motd = "New customer template"

            #initialize first utilbill here.
            #need to choose a default service
            #once the utilbill is initially created, we leave it to other processes to add services, etc..
            #utilbill section:
            #    "hypothetical_chargegroups" : {
            #        "All Charges" : [

            #consider a reset statistics function
            self.statistics = {
             "renewable_utilization" : None,
              "total_co2_offset" : None,
              "total_savings" : None,
              "conventional_consumed" : None,
              "conventional_utilization" : None,
              "consumption_trend" : [
                {
                    "quantity" : None,
                    "month" : "Nov"
                },
                {
                    "quantity" : None,
                    "month" : "Dec"
                },
                {
                    "quantity" : None,
                    "month" : "Jan"
                },
                {
                    "quantity" : None,
                    "month" : "Feb"
                },
                {
                    "quantity" : None,
                    "month" : "Mar"
                },
                {
                    "quantity" : None,
                    "month" : "Apr"
                },
                {
                    "quantity" : None,
                    "month" : "May"
                },
                {
                    "quantity" : None,
                    "month" : "Jun"
                },
                {
                    "quantity" : None,
                    "month" : "Jul"
                },
                {
                    "quantity" : None,
                    "month" : "Aug"
                },
                {
                    "quantity" : None,
                    "month" : "Sep"
                },
                {
                    "quantity" : None,
                    "month" : "Oct"
                }
              ],
              "total_trees" : None,
              "co2_offset" : None,
              "total_renewable_consumed" : None,
              "renewable_consumed" : None
            }


            self.actual_total = Decimal("0.00")
            self.hypothetical_total = Decimal("0.00")



        else:
            raise ValueError("Bad Parameter Value")



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
    def balance_due(self):
        '''Returns a Decimal.'''
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
    @check_issued
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

    def hypothetical_total_for_service(self, service_name):
        '''Returns the total of hypothetical charges for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        totals = [ub['hypothetical_total']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_hypothetical_total_for_service(self, service_name, new_total):

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['hypothetical_total'] = new_total

    def actual_total_for_service(self, service_name):
        '''Returns the total of actual charges for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        totals = [ub['actual_total']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_actual_total_for_service(self, service_name, new_total):

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['actual_total'] = new_total

    def ree_value_for_service(self, service_name):
        '''Returns the total of 'ree_value' (renewable energy value offsetting
        hypothetical charges) for the utilbill whose service is 'service_name'.
        There's not supposed to be more than one utilbill per service, so an
        exception is raised if that happens (or if there's no utilbill for that
        service).'''
        totals = [ub['ree_value']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_ree_value_for_service(self, service_name, new_ree_value):
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['ree_value'] = new_ree_value

    def ree_savings_for_service(self, service_name):
        totals = [ub['ree_savings']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_ree_savings_for_service(self, service_name, new_ree_savings):

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['ree_savings'] = new_ree_savings

    def ree_charges_for_service(self, service_name):
        totals = [ub['ree_charges']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_ree_charges_for_service(self, service_name, new_ree_charges):
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['ree_charges'] = new_ree_charges


    def hypothetical_chargegroups_for_service(self, service_name):
        '''Returns the list of hypothetical chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        chargegroup_lists = [ub['hypothetical_chargegroups']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if chargegroup_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(chargegroup_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)

        return chargegroup_lists[0]

    def set_hypothetical_chargegroups_for_service(self, service_name, new_chargegroups):
        '''Set hypothetical chargegroups, based on actual chargegroups.  This is used
        because it is customary to define the actual charges and base the hypothetical
        charges on them.'''
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['hypothetical_chargegroups'] = new_chargegroups

    def actual_chargegroups_for_service(self, service_name):
        '''Returns the list of actual chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        chargegroup_lists = [ub['actual_chargegroups']
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if chargegroup_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(chargegroup_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return chargegroup_lists[0]

    def set_actual_chargegroups_for_service(self, service_name, new_chargegroups):
        '''Set hypothetical chargegroups, based on actual chargegroups.  This is used
        because it is customary to define the actual charges and base the hypothetical
        charges on them.'''
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service_name:
                ub['actual_chargegroups'] = new_chargegroups

    def chargegroups_model_for_service(self, service_name):
        '''Returns a shallow list of chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        chargegroup_lists = [ub['actual_chargegroups'].keys()
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name]
        if chargegroup_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(chargegroup_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return chargegroup_lists[0]

    @property
    def services(self):
        '''Returns a list of all services for which there are utilbills.'''
        return [u['service'] for u in self.reebill_dict['utilbills']]

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
        per service, so an exception is raised if that happens (or if there's
        no utilbill for that service).'''
        date_string_pairs = [
            (
                u['period_begin'] if 'period_begin' in u else None,
                u['period_end'] if 'period_end' in u else None
            )  for u in self.reebill_dict['utilbills'] if u['service'] == service_name
        ]
        if date_string_pairs == []:
            raise Exception('No utilbills for service "%s"' % service_name)
        if len(date_string_pairs) > 1:
            raise Exception('Multiple utilbills for service "%s"' % service_name)
        start, end = date_string_pairs[0]

        # remember, mongo stores datetimes, but we only wish to treat dates here
        return (start, end)

    def set_utilbill_period_for_service(self, service_name, period):

        if service_name not in self.services:
            raise Exception('No such service "%s"' % service_name)

        if len(period) != 2:
            raise Exception('Utilbill period malformed "%s"' % period)
        
        for utilbill in self.reebill_dict['utilbills']:
            if utilbill['service'] == service_name:
                utilbill['period_begin'] = period[0]
                utilbill['period_end'] = period[1]

    @property
    def utilbill_periods(self):
        '''Return a dictionary whose keys are service and values the utilbill period.'''
        return dict([(service, self.utilbill_period_for_service(service)) for service in self.services])

    @utilbill_periods.setter
    def utilbill_periods(self, value):
        '''Set the utilbill periods based on a dictionary whose keys are service and values utilbill periods.'''

        for (service, period) in value.iteritems():
            self.set_utilbill_period_for_service(service, period)

    # TODO: consider calling this meter readings
    def meters_for_service(self, service_name):
        '''Returns the meters (a list of dictionaries) for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''

        meters_lists = [ub['meters'] for ub in self.reebill_dict['utilbills'] if
                ub['service'] == service_name]

        if meters_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(meters_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)

        return meters_lists[0]


    def meter(self, service, identifier):
        meter = next((meter for meter in self.meters_for_service(service) if meter['identifier'] == identifier), None)
        return meter

    def delete_meter(self, service, identifier):
        meters = self.meters_for_service(service)
        for meter in meters:
            print "meter['identifier'] %s %s" % (meter['identifier'], type(meter['identifier']))
            print "identifier %s %s" % (identifier, type(identifier))
            print "identifier == meter['identifier']  %s" % (identifier == meter['identifier'])
            print "identifier is meter['identifier']  %s" % (identifier is meter['identifier'])
        new_meters = [meter for meter in meters if meter['identifier'] != identifier]
        print "new set of meters %s" % new_meters
        
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service:
                ub['meters'] = new_meters

    def new_meter(self, service):

        new_meter = {
            'identifier': str(UUID.uuid4()),
            'present_read_date': None,
            'prior_read_date': datetime.now(),
            'estimated': False,
            'registers': [],
        }

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service:
                ub['meters'].append(new_meter)

        return new_meter

    def new_register(self, service, meter_identifier):
        
        identifier = str(UUID.uuid4())

        new_actual_register = {
            "description" : "No description",
            "quantity" : 0,
            "quantity_units" : "No Units",
            "shadow" : False,
            "identifier" : identifier,
            "type" : "total",
            "register_binding": "No Binding"
        }
        new_shadow_register = {
            "description" : "No description",
            "quantity" : 0,
            "quantity_units" : "No Units",
            "shadow" : True,
            "identifier" : identifier,
            "type" : "total",
            "register_binding": "No Binding"
        }

        # lookup meter and add these registers
        meter = self.meter(service, meter_identifier)

        meter['registers'].extend([new_actual_register, new_shadow_register])

        return (new_actual_register, new_shadow_register)

        
    

    def set_meter_read_date(self, service, identifier, present_read_date, prior_read_date):
        ''' Set the read date for a specified meter.'''

        for meter in self.meters_for_service(service):
            if meter['identifier'] == identifier:
                meter['present_read_date'] = present_read_date
                meter['prior_read_date'] = prior_read_date

    def set_meter_actual_register(self, service, meter_identifier, register_identifier, quantity):
        ''' Set the total for a specified meter register.'''

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service:
                for meter in ub['meters']:
                    if meter['identifier'] == meter_identifier:
                        for register in meter['registers']:
                            if (register['shadow'] == False) and (register['identifier'] == register_identifier):
                                register['quantity'] = quantity

    def set_meter_identifier(self, service, old_identifier, new_identifier):

        if old_identifier == new_identifier:
            return

        # TODO: 23251399 - probably need a better strategy to enforce uniqueness
        for meter in self.meters_for_service(service):
            if meter['identifier'] == new_identifier:
                raise Exception("Duplicate Identifier")

        for meter in self.meters_for_service(service):
            if meter['identifier'] == old_identifier:
                meter['identifier'] = new_identifier

    def set_register_identifier(self, service, old_identifier, new_identifier):

        if old_identifier == new_identifier:
            return

        # TODO: 23251399 - probably need a better strategy to enforce uniqueness
        for meter in self.meters_for_service(service):
            for register in meter['registers']:
                if register['identifier'] == new_identifier:
                    raise Exception("Duplicate Identifier")

        for meter in self.meters_for_service(service):
            for register in meter['registers']:
                if register['identifier'] == old_identifier:
                    # sets both actual and shadow regisers
                    register['identifier'] = new_identifier

    def meter_for_register(self, service, identifier):
        meters = self.meters_for_service(service)

        for meter in meters:
            for register in meter['registers']:
                if register['identifier'] == identifier:
                    return meter
    @property
    def meters(self):
        # TODO rename to something like meters_dict
        '''Returns a dictionary mapping service names to lists of meters.'''
        return dict([(service, self.meters_for_service(service)) for service in self.services])


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
        all_actual = []
        for meter in self.meters_for_service(service):
            all_actual.extend(filter(
                # this filter predicate works because any nonempty dictionary
                # happens to evaluate to True--but if a register dictionary
                # happens to be empty, it will disappear from the result.
                # (why would you write it like this?)
                lambda register: register if register['shadow'] is False else False,
                meter['registers']
            ))
        return all_actual


    # TODO: probably should be qualified by service since register identifiers could collide
    def set_actual_register_quantity(self, identifier, quantity):
        '''Sets the value 'quantity' in the first register subdictionary whose
        identifier is 'identifier' to 'quantity'. Raises an exception if no
        register with that identified is found.'''
        for service in self.services:
            for register in self.actual_registers(service):
                if register['identifier'] == identifier:
                    register['quantity'] = quantity
                    return
        raise Exception('No actual register found with identifier "%s"' % identifier)

    def shadow_registers(self, service):
        # TODO partially duplicates of
        # fetch_bill_data.get_shadow_register_data? move that function into
        # mongo.py to replace this one
        all_shadow = []
        for meter in self.meters_for_service(service):
            all_shadow.extend(filter(
                lambda register: register if register['shadow'] is True else False, meter['registers']
            ))
        return all_shadow

    # TODO: probably should be qualified by service since register identifiers could collide
    def set_shadow_register_quantity(self, identifier, quantity):
        '''Sets the value 'quantity' in the first register subdictionary whose
        identifier is 'identifier' to 'quantity'. Raises an exception if no
        register with that identified is found.'''
        for service in self.services:
            for register in self.shadow_registers(service):
                if register['identifier'] == identifier:
                    register['quantity'] = quantity
                    return
        raise Exception('No shadow register found with identifier "%s"' % identifier)

    def utility_name_for_service(self, service_name):
        try:
            utility_names = [
                ub['utility_name'] 
                for ub in self.reebill_dict['utilbills']
                # case-insensitive comparison
                if ub['service'].lower() == service_name.lower()
            ]
        except KeyError:
            # mongo reebills that came from xml reebills lacking "rsbinding" at
            # the utilbill root will lack a "utility_name" key
            raise NoUtilityNameError('this reebill lacks a utility name (from '
                    '"rsbinding" attribute at at bill/utilbill in xml).')

        if utility_names == []:
            raise Exception('No utility name found for service "%s"' % service_name)
        if len(utility_names) > 1:
            raise Exception('Multiple utility names for service "%s"' % service_name)
        return utility_names[0]

    def rate_structure_name_for_service(self, service_name):
        try:
            rs_bindings = [
                ub['rate_structure_binding'] 
                for ub in self.reebill_dict['utilbills']
                if ub['service'] == service_name
            ]
        except KeyError:
            # mongo reebills that came from xml reebills lacking "rsbinding" at
            # the utilbill root will lack a "rate_structure_binding" key
            raise NoRateStructureError('this reebill lacks a rate structure')

        if rs_bindings == []:
            raise Exception('No rate structure binding found for service "%s"' % service_name)
        if len(rs_bindings) > 1:
            raise Exception('Multiple rate structure bindings found for service "%s"' % service_name)
        return rs_bindings[0]

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
        for utilbill in self.reebill_dict['utilbills']:
            for meter in utilbill['meters']:
                for register in meter['registers']:
                    if register['shadow'] == True:
                        quantity = register['quantity']
                        unit = register['quantity_units'].lower()
                        if unit == 'therms':
                            total_therms += quantity
                        elif unit == 'btu':
                            total_therms += quantity / Decimal("100000.0")
                        elif unit == 'kwh':
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
    def hypothetical_chargegroups_flattened(self, service, chargegroups='hypothetical_chargegroups'):
        return self.chargegroups_flattened(service, chargegroups)

    def actual_chargegroups_flattened(self, service, chargegroups='actual_chargegroups'):
        return self.chargegroups_flattened(service, chargegroups)

    def chargegroups_flattened(self, service, chargegroups):

        # flatten structure into an array of dictionaries, one for each charge
        # this has to be done because the grid editor is  looking for a flat table
        # This should probably not be done in here, but rather by some helper object?

        flat_charges = []
        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service:
                for (chargegroup, charges) in ub[chargegroups].items(): 
                    for charge in charges:
                        charge['chargegroup'] = chargegroup
                        flat_charges.append(charge)

        return flat_charges

    def set_hypothetical_chargegroups_flattened(self, service, flat_charges, chargegroups='hypothetical_chargegroups'):
        return self.set_chargegroups_flattened(service, flat_charges, chargegroups)

    def set_actual_chargegroups_flattened(self, service, flat_charges, chargegroups='actual_chargegroups'):
        return self.set_chargegroups_flattened(service, flat_charges, chargegroups)

    def set_chargegroups_flattened(self, service, flat_charges, chargegroups):

        for ub in self.reebill_dict['utilbills']:
            if ub['service'] == service:
                # TODO sort flat_charges before groupby
                # They post sorted, but that is no guarantee...

                new_chargegroups = {}
                for cg, charges in it.groupby(flat_charges, key=lambda charge:charge['chargegroup']):
                    new_chargegroups[cg] = []
                    for charge in charges:
                        del charge['chargegroup']
                        #charge['quantity'] = charge['quantity']
                        #charge['rate'] = charge['rate']
                        #charge['total'] = charge['total']
                        new_chargegroups[cg].append(charge)

                ub[chargegroups] = new_chargegroups


class NoSuchReeBillException(Exception):
    pass

class ReebillDAO:
    '''A "data access object" for reading and writing reebills in MongoDB.'''

    def __init__(self, state_db, host='localhost', port=27017,
            database='reebills', **kwargs):
        self.state_db = state_db

        try:
            self.connection = pymongo.Connection(host, int(port)) 
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        finally:
            # TODO when to disconnect from the database?
            pass
        
        self.collection = self.connection[database]['reebills']

    def load_reebill(self, account, sequence, version='max'):
        '''Returns the reebill with the given account and sequence, and the
        greatest version by default. If 'version' is a specific version number,
        that version will be returned. If 'version' is a date, and there exist
        versions before that date, the greatest version issued before that date
        is chosen. Otherwise the greatest version overall will be returned.'''
        # TODO looks like somebody's temporary hack should be removed
        if account is None: return None
        if sequence is None: return None

        query = {
            "_id.account": str(account),
            # TODO stop passing in sequnce as a string from BillToolBridge
            "_id.sequence": int(sequence),
        }
        if isinstance(version, int):
            query.update({'_id.version': version})
            mongo_doc = self.collection.find_one(query)
        elif version == 'max':
            # get max version from MySQL, since that's the definitive source of
            # information on what officially exists
            with DBSession(self.state_db) as session:
                max_version = self.state_db.max_version(session, account, sequence)
                session.commit()
            query.update({'_id.version': max_version})
            mongo_doc = self.collection.find_one(query)
        elif isinstance(version, date):
            version_dt = date_to_datetime(version)
            docs = self.collection.find(query, sort=[('_id.version',
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
            raise NoSuchReeBillException(("No ReeBill found: query was %s")
                    % (query))

        mongo_doc = deep_map(float_to_decimal, mongo_doc)
        mongo_doc = convert_datetimes(mongo_doc) # this must be an assignment because it copies
        mongo_reebill = MongoReebill(mongo_doc)

        return mongo_reebill

    def load_reebills_for(self, account, version=0):
        # TODO remove--redundant with load_reebills_in_period when no dates are given, except for exclusion of sequence 0

        if not account: return None

        query = {
            "_id.account": str(account),
            '_id.version': version
        }

        mongo_docs = self.collection.find(query, sort=[("_id.sequence",pymongo.ASCENDING)])

        mongo_reebills = []
        for doc in mongo_docs:
            doc = deep_map(float_to_decimal, doc)
            doc = convert_datetimes(doc) # this must be an assignment because it copies
            mongo_reebills.append(MongoReebill(doc))

        return mongo_reebills
    
    def load_reebills_in_period(self, account, version=0, start_date=None,
            end_date=None):
        '''Returns a list of MongoReebills whose period began on or before
        'end_date' and ended on or after 'start_date' (i.e. all bills between
        those dates and all bills whose period includes either endpoint). The
        results are ordered by sequence. If 'start_date' and 'end_date' are not
        given or are None, the time period extends to the begining or end of
        time, respectively. Sequence 0 is never included.
        
        'version' may be a specific version number, or 'any' to get all
        versions.'''
        query = {
            '_id.account': str(account),
            '_id.sequence': {'$gt': 0},
        }
        if isinstance(version, int):
            query.update({'_id.version': version})
        elif version == 'any':
            pass
        else:
            raise ValueError('Unknown version specifier "%s"' % version)
        # TODO max version

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
        docs = self.collection.find(query).sort('sequence')
        for mongo_doc in self.collection.find(query):
            mongo_doc = convert_datetimes(mongo_doc)
            mongo_doc = deep_map(float_to_decimal, mongo_doc)
            result.append(MongoReebill(mongo_doc))
        return result
        
    def save_reebill(self, reebill, force=False):
        '''Saves the MongoReebill 'reebill' into the database. If a document
        with the same account, sequence, and version already exists, the existing
        document is replaced.
        
        Replacing an already-issued reebill (as determined by StateDB, using
        the rule that all versions except the highest are issued) is forbidden
        unless 'force' is True (this should only be used for testing).'''
        if not force:
            with DBSession(self.state_db) as session:
                if self.state_db.is_issued(session, reebill.account,
                        reebill.sequence, version=reebill.version,
                        allow_nonexistent=True):
                    raise Exception("Can't modify an issued reebill.")
                session.commit()
        
        mongo_doc = bson_convert(copy.deepcopy(reebill.reebill_dict))

        self.collection.save(mongo_doc)

    def delete_reebill(self, account, sequence, version):
        self.collection.remove({
            '_id.account': account,
            '_id.sequence': sequence,
            '_id.version': version,
        }, safe=True)

    def get_first_bill_date_for_account(self, account):
        '''Returns the start date of the account's earliest reebill, or None if
        no reebills exist for the customer.'''
        query = {
            '_id.account': account,
            '_id.sequence': 1,
        }
        result = self.collection.find_one(query)
        if result == None:
            return None
        return MongoReebill(result).period_begin

    def get_first_issue_date_for_account(self, account):
        '''Returns the issue date of the account's earliest reebill, or None if
        no reebills exist for the customer.'''
        query = {
            '_id.account': account,
            '_id.sequence': 1,
        }
        result = self.collection.find_one(query)
        if result == None:
            return None
        return MongoReebill(result).issue_date

    def last_sequence(self, account):
        '''Returns the sequence of the last reebill for the given account, or 0
        if no reebills were found. This is different from
        StateDB.last_sequence() because it uses Mongo; there may be un-issued
        reebills in Mongo that are not in MySQL.'''
        result = self.collection.find_one({
            '_id.account': account
            }, sort=[('sequence', pymongo.DESCENDING)])
        if result == None:
            return 0
        return MongoReebill(result).sequence

class NoRateStructureError(Exception):
    pass
class NoUtilityNameError(Exception):
    pass
