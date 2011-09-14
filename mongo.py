#!/usr/bin/python
import sys
import datetime
from datetime import date, time, datetime
from decimal import Decimal
import pymongo
import billing.bill as bill
from billing.mutable_named_tuple import MutableNamedTuple

from lxml import etree
from lxml.etree import _ElementStringResult
from exceptions import TypeError
from urlparse import urlparse
import httplib
import string
import base64
import itertools as it
import copy

import pdb
import pprint
pp = pprint.PrettyPrinter(indent=1)


# date format for returning parsing date strings read out of Mongo
DATE_FORMAT = '%Y-%m-%d'

# this dictionary maps XML element names to MongoDB document keys, for use in
# rename_keys(). element names that map to None will be removed instead of
# renamed.
# TODO maybe break into separate dictionaries used for each call to
# rename_keys()
name_changes = {
    # rebill section
    'serviceaddress': 'service_address',
    'billingaddress': 'billing_address',
    'priorbalance': 'prior_balance',
    'paymentreceived': 'payment_received',
    'totaladjustment': 'total_adjustment',
    'balanceforward': 'balance_forward',
    # same name for total of hypothetical/actual charges within a particular
    # utilbill and for over all utilbills in the whole reebill (so these are
    # also in the utilbill section)
    'hypotheticalecharges': 'hypothetical_total',
    'actualecharges': 'actual_total',
    'revalue': 'ree_value',
    'recharges': 'ree_charges',
    'resavings': 'ree_savings',
    'totaldue': 'total_due',
    'duedate': 'due_date',
    'issued': 'issue_date',
    # utilbill section
    'begin': 'period_begin',
    'end': 'period_end',
    'rsbinding': 'rsi_binding', # also in measuredusage section
    'rateunits': 'rate_units',
    'quantityunits': 'quantity_units',
    # measuredusage section
    'presentreaddate': 'present_read_date',
    'priorreaddate': 'prior_read_date',
    'inclusions':None,
    'exclusions':None,
    # statistics section
    'co2offset': 'co2_offset',
    'consumptiontrend': 'consumption_trend',
    'conventionalconsumed': 'conventional_consumed',
    'conventionalutilization': 'conventional_utilization',
    'renewableconsumed': 'renewable_consumed',
    'renewableproduced': 'renewable_produced',
    'renewableutilization': 'renewable_utilization',
    'totalco2offset': 'total_co2_offset',
    'totalrenewableconsumed': 'total_renewable_consumed',
    'totalsavings': 'total_savings',
    'totaltrees': 'total_trees'
}


def convert_old_types(x):
    '''Strip out the MutableNamedTuples since they are no longer 
    needed to preserve document order and provide dot-access notation.'''

    if type(x) in [str, float, int, bool]:
        return x
    if type(x) is Decimal:
        return x
    # lxml gives us string_result types for strings
    if type(x) is _ElementStringResult:
        return str(x)
    if type(x) is unicode:
        return str(x)
    if type(x) in [date, time]:
        return x
    if type(x) is dict or type(x) is MutableNamedTuple:
        return dict([(item[0], convert_old_types(item[1])) for item in x.iteritems()
                if item[1] is not None])
    if type(x) is list:
        return map(convert_old_types, x)

def bson_convert(x):
    '''Returns x converted into a type suitable for Mongo.'''
    # TODO:  copy all or convert all in place?  Or, don't care and just keep doing both
    # scalars are converted in place, dicts are copied.

    if type(x) in [str, float, int, bool, datetime, unicode]:
        return x
    if type(x) is Decimal:
        return float(x)
    if type(x) is time:
        return str(x)
    if type(x) is date:
        return datetime(x.year, x.month, x.day)
    if type(x) is dict or type(x) is MutableNamedTuple:
        #TODO: don't copy dict
        return dict([(item[0], bson_convert(item[1])) for item in x.iteritems()
                if item[1] is not None])
    if type(x) is list:
        return map(bson_convert, x)

    raise ValueError("type(%s) is %s: can't convert that into bson" \
            % (x, type(x)))

#TODO: looks like this makes a by value copy of a dictionary causing references to be lost
# making difficult returning references to data that needs to be modified. (e.g. we return
# a meter dict which might have an identifier changed)
# See set_meter_read_date()
def deep_map(func, x):
    '''Applies the function 'func' througout the data structure x, or just
    applies it to x if x is a scalar. Used for type conversions from Mongo
    types back into the appropriate Python types.'''
    if type(x) is list:
        return [deep_map(func, item) for item in x]
    if type(x) is dict:
        # this creates a new dictionary, we wish to use the one in place? Only if references are lost
        return dict((deep_map(func, key), deep_map(func, value)) for key, value in x.iteritems())
    return func(x)

def float_to_decimal(x):
    '''Converts float into Decimal. Used in getter methods.'''
    # str() tells Decimal to automatically figure out how many digts of
    # precision we want
    return Decimal(str(x)) if type(x) is float else x

def rename_keys(x,d=name_changes ):
    '''If x is a dictionary or list, recursively replaces keys in x according
    to 'name_changes' above.'''
    if type(x) is dict:
        the_dict = dict([(d.get(key,key), rename_keys(value)) \
                for (key,value) in x.iteritems() \
                if not (key in d and d[key] is None)])
        return the_dict 
    if type(x) is list:
        #return map(rename_keys, x)
        return [rename_keys(element) for element in x]
    return x

#def dict_merge(overwrite=False, *dicts):
def dict_merge(*dicts, **kwargs):
    '''Returns a dictionary consisting of the key-value pairs in all the
    dictionaries passed as arguments. These dictionaries must not share any
    keys.'''
    overwrite = kwargs.get('overwrite', False)
    if not overwrite:
        # throw exception if they have the same keys
        for d in dicts:
            for key in d.keys():
                for other in [other for other in dicts if other is not d]:
                    if key in other.keys():
                        raise ValueError('dictionaries share key "%s"' % key)
    result = {}
    for d in dicts:
        result.update(d)
    return result

def subdict(d, keys, ignore_missing=True):
    '''Returns the "sub-dictionary" of 'd' consisting only of items whose keys
    are in 'keys'. If 'ignore_missing' is False, a KeyError will be raised if
    'd' is missing any key in 'keys'; otherwise missing keys are just
    ignored.'''
    return dict((key,d[key]) for key in keys if not ignore_missing or (key in d))

class MongoReebill:
    '''Class representing the reebill data structure stored in MongoDB. All
    data is stored in 'dictionary', which is a Python dict that PyMongo could
    read/write directly from/to the database. Provides methods for extracting
    pieces of bill information.

    Design matters to work through:

        where type conversions occur - 
            Should only happen on load/save so that object references are not
            lost. Moreover, initial xml load provides preferred types such
            as Decimal and datetime.  
            The lifecycle should be:  load from source converting to preferred
            python types.  Use class.  save to source converting to preferred
            source types.  
            This is in opposition to doing type conversion on getter/setter
            invocation.

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
    '''

    def __init__(self, reebill_data):

        # if no xml_reebill is passed in, assume we are
        # having self.dictionary set externally because
        # the bill was found in mongo
        if type(reebill_data) is dict:
            self.dictionary = reebill_data
            return

        # ok, it is the old bill.py, and when we are no longer needing XML
        # all code below DIES!!!
        b = reebill_data

        # Load, binding to xml data and renaming keys
        
        # top-level reebill information:
        self.dictionary = dict_merge({
                'account': convert_old_types(b.account),
                'sequence': int(b.id),
                'branch': int(0),
                'service_address': b.service_address,
                'billing_address': b.billing_address
            },
            rename_keys(convert_old_types(b.rebill_summary))
        )

        # utilbill info from the actual "utilbill" section (service names
        # moved from keys of the utilbill_summary_charges dict into the
        # utilbills themselves)
        self.dictionary['utilbills'] = [dict_merge({'service':service},
                rename_keys(convert_old_types(b.utilbill_summary_charges[service]), d= {
                    # utilbill section
                    'begin': 'period_begin',
                    'end': 'period_end',
                    'rsbinding': 'utility_name', # also in measuredusage section
                    'rateunits': 'rate_units',
                    'quantityunits': 'quantity_units',
                    'revalue':'ree_value',
                    'recharges':'ree_charges',
                    'resavings':'ree_savings',
                    'actualecharges': 'actual_total',
                    'hypotheticalecharges': 'hypothetical_total'
                }))
                for service in b.utilbill_summary_charges.keys()]


        # utilbill info from "details", "measuredusage", and "statistics"
        # sections of XML ("billableusage" section is completely ignored)
        actual_details = b.actual_details
        hypothetical_details = b.hypothetical_details
        measured_usages = b.measured_usage
        for utilbill in self.dictionary['utilbills']:
            # get hypothetical details and actual details from bill.py
            this_bill_actual_details = actual_details[utilbill['service']]
            this_bill_hypothetical_details = \
                    hypothetical_details[utilbill['service']]

            # fill in utilbill
            utilbill.update({
                # this is the <name/> element in <rateschedule/> and is not used.
                #'rate_schedule_name': convert_old_types(this_bill_actual_details.rateschedule.name),
                
                # Don't fail here, since the rsbinding has already 
                # been placed in self.dictionary['utilbills']

                # fail if this bill doesn't have an rsbinding
                'rate_schedule_binding': this_bill_actual_details. \
                        rateschedule.rsbinding,
                # so-called rate structure/schedule binding ("rsbinding") in utilbill
                # is actually the name of the utility
                #'utility_name': this_bill_actual_details.rateschedule.rsbinding,
                # TODO add rate schedule (not all xml files have this)
                # 'rate_schedule': convert_old_types(b.rateschedule),

                # chargegroups are divided between actual and hypothetical; these are
                # stored in 2 dictionaries mapping the name of each chargegroup to a
                # list of its charges. totals (in the format {total: #}) are removed
                # from each list of charges and placed at the root of the utilbill.
                'actual_chargegroups': dict( 
                    (chargegroup.type, [rename_keys(convert_old_types(charge))
                    for charge in chargegroup.charges if charge.keys() != ['total']])
                    for chargegroup in this_bill_actual_details.chargegroups
                ),
                'actual_total': convert_old_types(this_bill_actual_details.total),
                'hypothetical_chargegroups': dict(
                    (chargegroup.type, [rename_keys(convert_old_types(charge))
                    for charge in chargegroup.charges if charge.keys() != ['total']])
                    for chargegroup in this_bill_hypothetical_details.chargegroups
                ),
                'hypothetical_total': convert_old_types(this_bill_hypothetical_details.total)
            })

            # measured usages: each utility has one or more meters, each of which has
            # one or more registers (which are like sub-meters)
            meters = measured_usages[utilbill['service']]
            # TODO replace register.inclusions/exclusions with a "descriptor"
            # (a name) that matches the value of 'descriptor' for a register in
            # the 'registers' section of the monthly rate structure yaml file. 
            utilbill.update({'meters': rename_keys(convert_old_types(meters))})

        # statistics: exactly the same as in XML
        self.dictionary['statistics'] = rename_keys(convert_old_types(b.statistics))

        # strip out the old types including  MutableNamedTuples, creating loss 
        # of being able to access data via dot-notation
        #new_dictionary = convert_old_types(self.dictionary)
        #self.dictionary = new_dictionary

    # methods for getting data out of the mongo document: these could change
    # depending on needs in render.py or other consumers. return values are
    # strings unless otherwise noted.
    
    @property
    def account(self):
        return self.dictionary['account']
    @account.setter
    def account(self, value):
        self.dictionary['account'] = value
    
    @property
    def sequence(self):
        return self.dictionary['sequence']
    @sequence.setter
    def sequence(self, value):
        self.dictionary['sequence'] = int(value)
    
    @property
    def issue_date(self):
        return datetime.strptime(self.dictionary['issue_date'], DATE_FORMAT).date()
    @issue_date.setter
    def issue_date(self, value):
        self.dictionary['issue_date'] = value

    @property
    def due_date(self):
        return datetime.strptime(self.dictionary['due_date'], DATE_FORMAT).date()
    @due_date.setter
    def due_date(self, value):
        self.dictionary['due_date'] = value

    @property
    def period_begin(self):
        return datetime.strptime(self.dictionary['period_begin'], DATE_FORMAT).date()
    @period_begin.setter
    def period_begin(self, value):
        self.dictionary['period_begin'] = value

    @property
    def period_end(self):
        return datetime.strptime(self.dictionary['period_end'], DATE_FORMAT).date()
    @period_end.setter
    def period_end(self, value):
        self.dictionary['period_end'] = value
    
    @property
    def balance_due(self):
        '''Returns a Decimal.'''
        return self.dictionary['total_due']
    @balance_due.setter
    def balance_due(self, value):
        self.dictionary['balance_due'] = value

    @property
    def billing_address(self):
        '''Returns a dict.'''
        return self.dictionary['billing_address']
    @billing_address.setter
    def billing_address(self):
        '''Returns a dict.'''
        self.dictionary['billing_address'] = value

    @property
    def service_address(self):
        '''Returns a dict.'''
        return self.dictionary['service_address']
    @service_address.setter
    def service_address(self, value):
        self.dictionary['service_address'] = value

    @property
    def prior_balance(self):
        return self.dictionary['prior_balance']
    @prior_balance.setter
    def prior_balance(self, value):
        self.dictionary['prior_balance'] = value

    @property
    def payment_received(self):
        return self.dictionary['payment_received']
    @payment_received.setter
    def payment_received(self, value):
        self.dictionary['payment_received'] = value

    @property
    def total_adjustment(self):
        return self.dictionary['total_adjustment']
    @total_adjustment.setter
    def total_adjustment(self, value):
        self.dictionary['total_adjustment'] = value

    @property
    def ree_charges(self):
        return self.dictionary['ree_charges']
    @ree_charges.setter
    def ree_charges(self, value):
        self.dictionary['ree_charges'] = value

    @property
    def ree_savings(self):
        return self.dictionary['ree_savings']
    @ree_savings.setter
    def ree_savings(self, value):
        self.dictionary['ree_savings'] = value

    @property
    def balance_forward(self):
        return self.dictionary['balance_forward']
    @balance_forward.setter
    def balance_forward(self, value):
        self.dictionary['balance_forward'] = value

    @property
    def motd(self):
        '''"motd" = "message of the day"; it's optional, so the reebill may not
        have one.'''
        return self.dictionary.get('message', '')
    @motd.setter
    def motd(self, value):
        self.dictionary['message'] = value

    @property
    def statistics(self):
        '''Returns a dictionary of the information that goes in the
        "statistics" section of reebill.'''
        return self.dictionary['statistics']
    @statistics.setter
    def statistics(self, value):
        self.dictionary['statistics'].update(value)

    @property
    def actual_total(self):
        return self.dictionary['actual_total']
    @actual_total.setter
    def actual_total(self):
        self.dictionary['actual_total'] = value

    @property
    def hypothetical_total(self):
        return self.dictionary['hypothetical_total']
    @hypothetical_total.setter
    def hypothetical_total(self):
        self.dictionary['hypothetical_total'] = value

    @property
    def ree_value(self):
        return self.dictionary['ree_value']
    @ree_value.setter
    def ree_value(self):
        self.dictionary['ree_value'] = value

    def hypothetical_total_for_service(self, service_name):
        '''Returns the total of hypothetical charges for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        totals = [ub['hypothetical_total']
                for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def actual_total_for_service(self, service_name):
        '''Returns the total of actual charges for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        totals = [ub['actual_total']
                for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def set_actual_total_for_service(self, service_name, new_total):

        old_total = self.actual_total_for_service(service_name)
        total = new_total

    def ree_value_for_service(self, service_name):
        '''Returns the total of 'ree_value' (renewable energy value offsetting
        hypothetical charges) for the utilbill whose service is 'service_name'.
        There's not supposed to be more than one utilbill per service, so an
        exception is raised if that happens (or if there's no utilbill for that
        service).'''
        totals = [ub['ree_value']
                for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
        if totals == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(totals) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return totals[0]

    def hypothetical_chargegroups_for_service(self, service_name):
        '''Returns the list of hypothetical chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        chargegroup_lists = [ub['hypothetical_chargegroups']
                for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
        if chargegroup_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(chargegroup_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return chargegroup_lists[0]

    def actual_chargegroups_for_service(self, service_name):
        '''Returns the list of actual chargegroups for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''
        chargegroup_lists = [ub['actual_chargegroups']
                for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
        if chargegroup_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(chargegroup_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)
        return chargegroup_lists[0]

    

    @property
    def services(self):
        '''Returns a list of all services for which there are utilbills.'''
        return list(set([u['service'] for u in self.dictionary['utilbills']]))

    def utilbill_period_for_service(self, service_name):
        '''Returns start & end dates of the first utilbill found whose service
        is 'service_name'. There's not supposed to be more than one utilbill
        per service, so an exception is raised if that happens (or if there's
        no utilbill for that service).'''
        date_string_pairs = [(u['period_begin'], u['period_end'])
                for u in self.dictionary['utilbills'] if u['service'] == service_name]
        if date_string_pairs == []:
            raise Exception('No utilbills for service "%s"' % service_name)
        if len(date_string_pairs) > 1:
            raise Exception('Multiple utilbills for service "%s"' % service_name)
        start, end = date_string_pairs[0]
        #return (datetime.strptime(start, DATE_FORMAT).date(),
        #        datetime.strptime(end, DATE_FORMAT).date())
        return (start, end)

    def set_utilbill_period_for_service(self, service_name, period):

        if service_name not in self.services:
            raise Exception('No such service "%s"' % service_name)

        if len(period) != 2:
            raise Exception('Utilbill period malformed "%s"' % period)
        
        for utilbill in self.dictionary['utilbills']:
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
        
    def meters_for_service(self, service_name):
        '''Returns the meters (a list of dictionaries) for the utilbill whose
        service is 'service_name'. There's not supposed to be more than one
        utilbill per service, so an exception is raised if that happens (or if
        there's no utilbill for that service).'''

        meters_lists = [ub['meters'] for ub in self.dictionary['utilbills'] if
                ub['service'] == service_name]

        if meters_lists == []:
            raise Exception('No utilbills found for service "%s"' % service_name)
        if len(meters_lists) > 1:
            raise Exception('Multiple utilbills found for service "%s"' % service_name)

        return meters_lists[0]

    def set_meter_read_date(self, service, identifier, present_read_date, prior_read_date):
        ''' Set the read date for a specified meter.'''

        # Would like to call meters_of_service but deep_map or someone seems to return copies
        # breaking reference to self.dictionary
        #for ub in self.dictionary['utilbills']:
        #    if ub['service'] == service:
        #for meter in ub['meters']:

        for meter in self.meters_for_service(service):
            if meter['identifier'] == identifier:
                meter['present_read_date'] = present_read_date
                meter['prior_read_date'] = prior_read_date

    def set_meter_actual_register(self, service, meter_identifier, register_identifier, total):
        ''' Set the total for a specified meter register.'''

        # Would like to call meters_of_service but deep_map or someone seems to return copies
        # breaking reference to self.dictionary
        for ub in self.dictionary['utilbills']:
            if ub['service'] == service:
                for meter in ub['meters']:
                    if meter['identifier'] == meter_identifier:
                        for register in meter['registers']:
                            if (register['shadow'] == False) and (register['identifier'] == register_identifier):
                                register['total'] = total

    @property
    def meters(self):
        return dict([(service, self.meters_for_service(service)) for service in self.services])

    def rsbinding_for_service(self, service_name):
        '''
        Return the rate structure binding for a given service
        '''

        rs_bindings = [
            ub['utility_name'] 
            for ub in self.dictionary['utilbills']
            if ub['service'] == service_name
        ]

        if rs_bindings == []:
            raise Exception('No rate structure binding found for service "%s"' % service_name)
        if len(rs_bindings) > 1:
            raise Exception('Multiple rate structure bindings found for service "%s"' % service_name)
        return rs_bindings[0]

    #
    # Helper functions
    #

    def hypothetical_chargegroups_flattened(self, service, chargegroups='hypothetical_chargegroups'):
        return self.chargegroups_flattened(service, chargegroups)

    def actual_chargegroups_flattened(self, service, chargegroups='actual_chargegroups'):
        return self.chargegroups_flattened(service, chargegroups)

    def chargegroups_flattened(self, service, chargegroups):

        # flatten structure into an array of dictionaries, one for each charge
        # this has to be done because the grid editor is  looking for a flat table
        # This should probably not be done in here, but rather by some helper object?

        flat_charges = []
        for ub in self.dictionary['utilbills']:
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

        for ub in self.dictionary['utilbills']:
            if ub['service'] == service:
                # TODO sort flat_charges before groupby
                # They post sorted, but that is no guarantee...

                new_chargegroups = {}
                for cg, charges in it.groupby(flat_charges, key=lambda charge:charge['chargegroup']):
                    new_chargegroups[cg] = []
                    for charge in charges:
                        del charge['chargegroup']
                        charge['quantity'] = charge['quantity']
                        charge['rate'] = charge['rate']
                        charge['total'] = charge['total']
                        new_chargegroups[cg].append(charge)

                ub[chargegroups] = new_chargegroups

class ReebillDAO:
    '''A "data access object" for reading and writing reebills in MongoDB.'''

    def __init__(self, config):

        self.config = config

        self.connection = None

        try:
            self.connection = pymongo.Connection(self.config['host'], int(self.config['port'])) 
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        finally:
            if self.connection is not None:
                #self.connection.disconnect()
                # TODO when to disconnect from the database?
                pass
        
        self.collection = self.connection[self.config['database']][self.config['collection']]
    

    def load_reebill(self, account, sequence, branch=0):

        mongo_doc = self.collection.find_one({"_id": {
            "account": str(account), 
            "branch": int(branch),
            "sequence": int(sequence)
        }})

        # didn't find one in mongo, so let's grab it from eXist
        # TODO: why not also save it into mongo and reload from mongo? for migration?

        if mongo_doc is None:
            b = self.load_xml_reebill(account, sequence)
            xml_reebill = MongoReebill(b)
            return xml_reebill
        else:
            mongo_doc = copy.deepcopy(deep_map(float_to_decimal, mongo_doc))
            mongo_reebill = MongoReebill(mongo_doc)
            return mongo_reebill
        
    def load_xml_reebill(self, account, sequence, branch=0):
        # initialization with a string: URL of an XML reebill in Exist. use
        # bill.py to extract information from it into self.dictionary.

        url = "%s/%s/%s.xml" % (self.config['destination_prefix'], account, sequence)

        # make a Bill object from the XML document
        b = bill.Bill(url)

        return b

    def save_reebill(self, reebill):
        '''Saves the MongoReebill 'reebill' into the database. If a document
        with the same account & sequence number already exists, the existing
        document is replaced with this one.'''

        mongo_doc = bson_convert(copy.deepcopy(reebill.dictionary))
        mongo_doc['_id'] = {'account': reebill.account,
            'sequence': reebill.sequence,
            'branch': 0}

        self.collection.save(mongo_doc)

    def save_xml_reebill(self, xml_reebill, account, sequence):

        url = "%s/%s/%s.xml" % (self.config["destination_prefix"], account, sequence)

        parts = urlparse(url)

        xml = xml_reebill.xml()

        if (parts.scheme == 'http'): 
            # http scheme URL, PUT to eXistDB

            con = httplib.HTTPConnection(parts.netloc)
            con.putrequest('PUT', '%s' % url)
            con.putheader('Content-Type', 'text/xml')

            auth = 'Basic ' + string.strip(base64.encodestring(self.config['user'] + ':' + self.config['password']))
            con.putheader('Authorization', auth )

            clen = len(xml) 
            con.putheader('Content-Length', clen)
            con.endheaders() 
            con.send(xml)
            response = con.getresponse()
            print str(response.status) + " " + response.reason

            print >> sys.stderr, url

        else:
            pass

if __name__ == '__main__':

    dao = ReebillDAO({
        "host":"localhost", 
        "port":27017, 
        "database":"skyline", 
        "collection":"reebills", 
        "destination_prefix":"http://localhost:8080/exist/rest/db/skyline/bills"
    })

    reebill = dao.load_reebill("10002","16")

    pp.pprint(reebill)

    print reebill.utilbill_period_for_service("Gas")

    #dao.save_reebill(reebill)



