#!/usr/bin/python
import sys
import datetime
from datetime import date, time, datetime
from decimal import Decimal
import pymongo
import billing.bill as bill
from billing.mutable_named_tuple import MutableNamedTuple

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
    'paymentrecieved': 'payment_recieved',
    'totaladjustment': 'total_adjustment',
    'balanceforward': 'balance_forward',
    'hypotheticalecharges': None, # identical to hypothetical_total
    'actualecharges': None, # identical to actual_total
    'revalue': 'ree_value',
    'recharges': 'ree_charges',
    'resavings': None,
    'totaldue': 'total_due',
    'duedate': 'due_date',
    'issued': 'issue_date',
    # utilbill section
    'periodstart': 'periodend',
    'periodend': 'periodstart',
    'rsbinding': 'rate_structure_binding', # also in measuredusage section
    'rateunits': 'rate_units',
    'quantityunits': 'rate_units',
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

def bson_convert(x):
    '''Returns x converted into a type suitable for Mongo.'''
    if type(x) in [str, float, int, bool]:
        return x
    if type(x) is Decimal:
        return float(x)
    if type(x) in [date, time]:
        return str(x)
    if type(x) is dict or type(x) is MutableNamedTuple:
        return dict([(item[0], bson_convert(item[1])) for item in x.iteritems()
                if item[1] is not None])
    if type(x) is list:
        return map(bson_convert, x)
    raise ValueError("type(%s) is %s: can't convert that into bson" \
            % (x, type(x)))

def deep_map(func, x):
    '''Applies the function 'func' througout the data structure x, or just
    applies it to x if x is a scalar.wUsed for type conversions from Mongo
    types back into the appropriate Python types.'''
    if type(x) is list:
        return [deep_map(func, item) for item in x]
    if type(x) is dict:
        return {deep_map(func, key): deep_map(func, value) for key, value in x.iteritems()}
    return func(x)

def float_to_decimal(x):
    '''Converts float into Decimal. Used in getter methods.'''
    # str() tells Decimal to automatically figure out how many digts of
    # precision we want
    return Decimal(str(x)) if type(x) is float else x

def rename_keys(x):
    '''If x is a dictionary or list, recursively replaces keys in x according
    to 'name_changes' above.'''
    if type(x) is dict:
        return dict([(name_changes.get(key,key), rename_keys(value)) \
                for (key,value) in x.iteritems() \
                if not (key in name_changes and name_changes[key] is None)])
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
    return {key:d[key] for key in keys if not ignore_missing or (key in d)}

class MongoReebill:
    '''Class representing the reebill data structure stored in MongoDB. All
    data is stored in 'dictionary', which is a Python dict that PyMongo could
    read/write directly from/to the database. Provides methods for extracting
    pieces of bill information.'''

    def __init__(self, url):
        # initialization with a string: URL of an XML reebill in Exist. use
        # bill.py to extract information from it into self.dictionary.
        
        # make a Bill object from the XML document
        b = bill.Bill(url)

        # top-level reebill information:
        self.dictionary = dict_merge({
                'account': b.account,
                'sequence': b.id,
                'service_address': b.service_address,
                'billing_address': b.billing_address
            },
            rename_keys(bson_convert(b.rebill_summary))
        )

        # TODO
        '''
        replacement for utilbill.rate_structure_binding:
            utility_name: e.g. "washgas",
            rate_schedule: "DC_NONRESIDENTIAL_NONHEAT",
        '''

        '''
        A reebill has a list containing 1 or more utilbills, each of which is
        structured as follows:
           {
            ----- from utilbill section -----
            service: "",  <--moved into the utilbill itself
            ree_charges: #,
            ree_value: #,
            ----- from details section -----
            actual_chargegroups: [
              chargegroup_type: [
                       {    
                           description: ""
                           quantity: #
                           quantity_units: ""
                           rate: #
                           rate_schedule_binding: ""
                           rate_units: ""
                           total: #
                       },
                   ]
               ...
              ],
              ...
            ]
            actual_total: #
            hypothetical_chargegroups: (just like actual_chargegroups)
            hypothetical_total: #
            ----- from measuredusages section -----
            meters: {
              {service_name:
                  [identifier: "",
                   present_read_date: date,
                   prior_read_date: date,
                   registers: [
                      {description: ""
                       identifier: ""
                       presentreading: #
                       rate_schedule_binding: ""
                       shadow: boolean
                       total: #
                       type: ""
                       units: ""
                       }
                       ...
                   ]
                   ...
                 }
              }
            ----- statistics section -----
            (exactly the same as XML)
           }
        '''

        # utilbill info from the actual "utilbill" section (service names
        # moved from keys of the utilbill_summary_charges dict into the
        # utilbills themselves)
        self.dictionary['utilbills'] = [dict_merge({'service':service}, 
                rename_keys(bson_convert(b.utilbill_summary_charges[service])))
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
                'rate_schedule_name': this_bill_actual_details.rateschedule.name,
                
                # fail if this bill doesn't have an rsbinding
                'rate_schedule_binding': this_bill_actual_details. \
                        rateschedule.rsbinding,
                # so-called rate structure/schedule binding ("rsbinding") in utilbill
                # is actually the name of the utility
                'utility_name': this_bill_actual_details.rateschedule.rsbinding,
                # TODO add rate schedule (not all xml files have this)
                # 'rate_schedule': bson_convert(b.rateschedule),

                # chargegroups are divided between actual and hypothetical; these are
                # stored in 2 dictionaries mapping the name of each chargegroup to a
                # list of its charges. totals (in the format {total: #}) are removed
                # from each list of charges and placed at the root of the utilbill.
                'actual_chargegroups': {
                    chargegroup.type: [rename_keys(bson_convert(charge))
                    for charge in chargegroup.charges if charge.keys() != ['total']]
                    for chargegroup in this_bill_actual_details.chargegroups
                },
                'actual_total': bson_convert(this_bill_actual_details.total),
                'hypothetical_chargegroups': {
                    chargegroup.type: [rename_keys(bson_convert(charge))
                    for charge in chargegroup.charges if charge.keys() != ['total']]
                    for chargegroup in this_bill_hypothetical_details.chargegroups
                },
                'hypothetical_total': bson_convert(this_bill_hypothetical_details.total)
            })

            # measured usages: each utility has one or more meters, each of which has
            # one or more registers (which are like sub-meters)
            meters = measured_usages[utilbill['service']]
            # TODO replace register.inclusions/exclusions with a "descriptor"
            # (a name) that matches the value of 'descriptor' for a register in
            # the 'registers' section of the monthly rate structure yaml file. 
            utilbill.update({'meters': rename_keys(bson_convert(meters))})

        # statistics: exactly the same as in XML
        self.dictionary.update(rename_keys(bson_convert(b.statistics)))
        
    
    def insert(self):
        '''Inserts this document into the database. If a document with this
        account & sequence number already exists, the existing document is
        replaced with this one.'''
        # TODO don't use hard-coded database info
        
        # connect to mongo
        connection = None
        try:
            connection = pymongo.Connection('localhost', 27017) 
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        finally:
            if connection is not None:
                connection.disconnect()

        # if there's an existing document with the same account and sequence
        # numbers, remove it
        # TODO is it bad to replace the document instead of updating it?
        existing_document = connection.skyline.reebills.find_one({
            'account': self.account_number,
            'sequence': self.sequence_number
        })
        if existing_document is not None:
            # note that existing_document is a dict
            connection.skyline.reebills.remove(existing_document['_id'], save=True)

        # now insert the new document
        connection.skyline.reebills.insert(self.dictionary)
    


    # methods for getting data out of the mongo document: these could change
    # depending on needs in render.py or other consumers. return values are
    # strings unless otherwise noted.
    
    @property
    def account_number(self):
        return self.dictionary['account']
    @account_number.setter
    def account_number(self, value):
        self.dictionary['account'] = bson_convert(value)
    
    @property
    def sequence_number(self):
        return self.dictionary['sequence']
    @sequence_number.setter
    def sequence_number(self, value):
        self.dictionary['sequence'] = bson_convert(value)
    
    @property
    def issue_date(self):
        return datetime.strptime(self.dictionary['issue_date'], DATE_FORMAT).date()
    @issue_date.setter
    def issue_date(self, value):
        self.dictionary['issue_date'] = bson_convert(value)

    @property
    def due_date(self):
        return datetime.strptime(self.dictionary['due_date'], DATE_FORMAT).date()
    @due_date.setter
    def due_date(self, value):
        self.dictionary['due_date'] = bson_convert(value)
    
    @property
    def balance_due(self):
        '''Returns a Decimal.'''
        return float_to_decimal(self.dictionary['total_due'])
    @balance_due.setter
    def balance_due(self, value):
        self.dictionary['balance_due'] = bson_convert(value)

    @property
    def billing_address(self):
        '''Returns a dict.'''
        return self.dictionary['billing_address']
    @billing_address.setter
    def billing_address(self):
        '''Returns a dict.'''
        self.dictionary['billing_address'] = bson_convert(value)

    @property
    def service_address(self):
        '''Returns a dict.'''
        return self.dictionary['service_address']
    @service_address.setter
    def service_address(self, value):
        self.dictionary['service_address'] = bson_convert(value)

    @property
    def prior_balance(self):
        return float_to_decimal(self.dictionary['prior_balance'])
    @prior_balance.setter
    def prior_balance(self, vlaue):
        self.dictionary['prior_balance'] = bson_convert(value)

    @property
    def payment_received(self):
        return float_to_decimal(self.dictionary['payment_received'])
    @payment_received.setter
    def payment_received(self, vlaue):
        self.dictionary['payment_received'] = bson_convert(value)

    @property
    def total_adjustment(self):
        return float_to_decimal(self.dictionary['total_adjustment'])
    @total_adjustment.setter
    def total_adjustment(self, vlaue):
        self.dictionary['total_adjustment'] = bson_convert(value)

    @property
    def ree_charges(self):
        return float_to_decimal(self.dictionary['ree_charges'])
    @ree_charges.setter
    def total_adjustment(self, vlaue):
        self.dictionary['ree_charges'] = bson_convert(value)

    @property
    def ree_savings(self):
        return float_to_decimal(self.dictionary['ree_savings'])
    @ree_savings.setter
    def total_adjustment(self, vlaue):
        self.dictionary['ree_savings'] = bson_convert(value)

    @property
    def balance_forward(self):
        return float_to_decimal(self.dictionary['balance_forward'])
    @balance_forward.setter
    def total_adjustment(self, value):
        self.dictionary['balance_forward'] = bson_convert(value)

    @property
    def motd(self):
        '''Apparently "motd" stands for "message of the day".'''
        return self.dictionary['message']
    @motd.setter
    def total_adjustment(self, value):
        self.dictionary['message'] = bson_convert(value)

    @property
    def statistics(self):
        '''Returns a dictionary of the information that goes in the "statistics" section of reebill.'''
        return deep_map(float_to_decimal, subdict(self.dictionary, ['conventional_consumed',
            'renewable_consumed', 'renewable_utilization',
            'conventional_utilization', 'co2_offset',
            'total_savings', 'total_renewable_consumed',
            'total_renewable_produced', 'total_trees', 'total_co2_offset', 'consumption_trend']))
    @statistics.setter
    def statistics(self, value):
        self.dictionary['statistics'].update(bson_convert(value))

    # TODO: convert float into Decimal in these methods
    def actual_chargegroups_for_service(self, service_name):
        '''Returns a dictionary.'''
        return [ub['actual_chargegroups'] for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
    def actual_totals_for_service(self, service_name):
        return [ub['actual_total'] for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
    def hypothetical_chargegroups_for_service(self, service_name):
        '''Returns a dictionary.'''
        return [ub['hypothetical_chargegroups'] for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]
    def hypothetical_totals_for_service(self, service_name):
        return [ub['hypothetical_total'] for ub in self.dictionary['utilbills']
                if ub['service'] == service_name]

    @property
    def all_services(self):
        '''Returns a list of all services for which there are utilbills.'''
        return list(set([u['service'] for u in self.dictionary['utilbills']]))

    def utilbill_periods(self, service_name):
        '''Returns start & end dates of the first utilbill found whose service
        is 'service_name'. There's not supposed to be more than one utilbill
        per service, so an exception is raised if that happens (or if there's
        no utilbill for that service).'''
        dates = [(u['period_begin'], u['period_end'])
                for u in utilbills if u['service'] == service_name]
        if dates == []:
            raise Exception('No utilbills for service "%s"' % service_name)
        if len(dates) > 1:
            raise Exception('Multiple utilbills for service "%s"' % service_name)
        return datetime.strptime(dates[0], DATE_FORMAT)
