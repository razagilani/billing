#!/usr/bin/python
from __future__ import division
from datetime import datetime, date
from collections import defaultdict
from decimal import Decimal
import copy
import inspect
import jinja2
import os
import pymongo
import sys
import traceback
import uuid
import yaml
import yaml
from math import sqrt, log, exp
from billing.util.mongo_utils import bson_convert, python_convert, format_query
from billing.processing.exceptions import RSIError, RecursionError, NoPropertyError, NoSuchRSIError, BadExpressionError

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

# minimum normlized score for an RSI to get included in a probable UPRS
# (between 0 and 1)
RSI_PRESENCE_THRESHOLD = 0.5

def euclidean_distance(p1, p2):
    delta_begin = abs(p1[0] - p2[0]).days
    delta_end = abs(p1[1] - p2[1]).days
    return sqrt(delta_begin**2 + delta_end**2)

def manhattan_distance(p1, p2):
    # note that 15-day offset is a 30-day distance, 30-day offset is a
    # 60-day difference
    delta_begin = abs(p1[0] - p2[0]).days
    delta_end = abs(p1[1] - p2[1]).days
    return delta_begin + delta_end

def gaussian(height, center, fwhm):
    def result(x):
        sigma =  fwhm / 2 * sqrt(2 * log(2))
        return height * exp(- (x - center)**2 / (2 * sigma**2))
    return result

def exp_weight(a, b):
    return lambda x: a**(x * b)

def exp_weight_with_min(a, b, minimum):
    '''Exponentially-decreasing weight function with a minimum value so it's
    always nonnegative.'''
    return lambda x: max(a**(x * b), minimum)

class RateStructureDAO(object):
    '''
    Manages loading and saving rate structures.

    Rate structures are composites from three sources:
    URS - Utility Rate Structure 
    - bill cycle independent global data
    - contains meter requirements to be satisfied by a ReeBill
    - contains RS name and information about the effective period for the  URS
    UPRS - Utility Periodic Rate Structure 
    - bill cycle dependent global data
    - typically contains monthly rate data
    CPRS - Customer Periodic Rate Structure 
    - bill cycle data specific to customer
    - typically contains one or two corrections to accurately compute bill

    When a rate structure is requested for a given ReeBill, the URS is first 
    looked up and its keys merged with what is found in the UPRS and then
    CPRS.  This way, the CPRS augments the UPRS which overrides the URS.

    There will be rules to how this augmentation works.
        Matching keys might just be outright replaced
        Matching keys might have their values be merged into a list
        Matching keys might be renamed

    When the URS, UPRS and CPRS are merged, a probable rate structure exists.
    It may be used to calculate a bill, or prompt a user for additional 
    processing information.
    '''

    def __init__(self, host, port, database, **kwargs):
        '''kwargs catches extra junk from config dictionary unpacked into
        constructor arguments.'''
        try:
            self.connection = pymongo.Connection(host, int(port))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        self.database = self.connection[database]
        self.collection = self.database['ratestructure']

    def _get_probable_rsis(self, utility, rate_structure_name, period,
            distance_func=manhattan_distance,
            weight_func=exp_weight_with_min(0.5, 7, 0.000001),
            threshold=RSI_PRESENCE_THRESHOLD, ignore=lambda x: False):
        '''Returns list of RSI dictionaries: a guess of what RSIs will be in a
        new bill for the given rate structure during the given period. The list
        will be empty if no guess could be made. 'threshold' is the minimum
        score (between 0 and 1) for an RSI to be included. 'ignore' is an
        optional function to exclude UPRSs from the input data (used for
        testing).'''
        # load all UPRSs (to avoid repeated queries)
        all_uprss = [uprs for uprs in self.load_uprss(utility,
                rate_structure_name) if not ignore(uprs)]

        # find every RSI binding that ever existed for this rate structure
        bindings = set()
        for uprs in all_uprss:
            for rsi in uprs['rates']:
                bindings.add(rsi['rsi_binding'])
        
        # for each UPRS period, update the presence/absence score, total
        # presence/absence weight (for normalization), and full RSI dictionary
        # for the occurrence of each RSI binding closest to the target period
        scores = defaultdict(lambda: 0)
        total_weight = defaultdict(lambda: 0)
        closest_occurrence = defaultdict(lambda: (sys.maxint, None))
        for binding in bindings:
            for uprs in all_uprss:
                uprs_period = (uprs['_id']['effective'].date(),
                        uprs['_id']['expires'].date())

                # calculate weighted distance of this UPRS period from the
                # target period
                distance = distance_func(uprs_period, period)
                weight = weight_func(distance)

                # update score and total weight for this binding
                try:
                    rsi_dict = next(rsi for rsi in uprs['rates'] if
                            rsi['rsi_binding'] == binding)
                    # binding present in UPRS: add 1 * weight to score
                    scores[binding] += weight

                    # if this distance is closer than the closest occurence seen so
                    # far, put the RSI dictionary in closest_occurrence
                    if distance < closest_occurrence[binding][0]:
                        closest_occurrence[binding] = (distance, rsi_dict)
                except StopIteration:
                    # binding not present in UPRS: add 0 * weight to score
                    pass
                # whether the binding was present or not, update total weight
                total_weight[binding] += weight


        # include in the result all RSI bindings whose normalized weight
        # exceeds 'threshold', with the rate and quantity formulas it had in
        # its closest occurrence.
        result = []
        for binding, weight in scores.iteritems():
            normalized_weight = weight / total_weight[binding] if \
                    total_weight[binding] != 0 else 0
            print '%35s %.02f %d' % (binding, weight, 100 * normalized_weight)

            # note that total_weight[binding] will never be 0 because it must
            # have occurred somewhere in order to occur in 'scores'
            if normalized_weight >= threshold:
                rsi_dict = closest_occurrence[binding][1]
                rate, quantity = 0, 0
                try:
                    rate = rsi_dict['rate']
                    quantity = closest_occurrence[binding][1]['quantity']
                except KeyError:
                    pass
                    #print >> sys.stderr, 'malformed RSI:', rsi_dict
                result.append({
                    'rsi_binding': binding,
                    'rate': rate,
                    'quantity': quantity,
                    #'total': 0,
                    'uuid': uuid.uuid1(), # uuid1 is used in wsgi.py
                })
        return result

    def get_probable_uprs(self, reebill, service):
        '''Returns a guess of the rate structure for the given reebill.'''
        utility = reebill.utility_name_for_service(service)
        rate_structure_name = reebill.rate_structure_name_for_service(service)
        return {
            '_id': {
                'account': reebill.account,
                'sequence': reebill.sequence,
                'version': reebill.version,
                'utility_name': utility,
                'rate_structure_name': rate_structure_name,
            },
            'rates': self._get_probable_rsis(utility, rate_structure_name,
                    reebill.utilbill_period_for_service(service))
        }

    def _load_combined_rs_dict(self, reebill, service):
        '''Returns a dictionary of combined rate structure (derived from URS,
        UPRS, and CPRS) that should be used to compute the charges of
        'reebill'.'''
        # return a probable rate structure for each utilbill in the reebill
        # all the data needed to identify a probable rate structure
        account = reebill.account
        sequence = reebill.sequence
        version = reebill.version
        rsbinding = reebill.rate_structure_name_for_service(service)
        utility_name = reebill.utility_name_for_service(service)
        rate_structure_name = reebill.rate_structure_name_for_service(service)
        period_begin, period_end = reebill.utilbill_period_for_service(service)

        # load the URS
        urs = self.load_urs(utility_name, rate_structure_name, period_begin,
                period_end)
        if urs is None:
            raise ValueError(("Could not find URS for utility_name %s, "
                    "rate_structure_name %s, period %s - %s") % (utility_name,
                    rate_structure_name, period_begin, period_end))

        # remove the mongo key, because the requester already has this
        # information and we do not want application code depending on the
        # "_id" field.
        del urs['_id']

        # remove uuids because they are not used in rate structure computation
        for urs_rate in urs['rates']:
            del urs_rate['uuid']

        for urs_reg in urs['registers']:
            del urs_reg['uuid']

        # load the UPRS
        uprs = self.load_uprs(reebill.account, reebill.sequence,
                reebill.version, utility_name, rate_structure_name)

        # remove the mongo key, because the requester already has this
        # information and we do not want application code depending on the
        # "_id" field.
        del uprs['_id']

        # remove the uuids because they are not used in rate structure
        # computation
        if 'rates' in uprs:
            for uprs_rate in uprs['rates']:
                del uprs_rate['uuid']

        # load the CPRS
        cprs = self.load_cprs(account, sequence, version, utility_name,
                rate_structure_name)

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
        if cprs is None:
            import ipdb; ipdb.set_trace()
        del cprs['_id']

        # remove the uuids because they are not used in rate structure computation
        if 'rates' in cprs:
            for cprs_rate in cprs['rates']:
                del cprs_rate['uuid']

        # URS is overridden and augmented by rates in UPRS

        # for each UPRS rate, find URS rate and override/augment it
        if 'rates' in uprs:
            for uprs_rate in uprs['rates']:
                # find a matching rate in URS
                urs_rate = [rate for rate in urs['rates'] if
                        rate['rsi_binding'] == uprs_rate['rsi_binding']]
                # URS does not have a rate for UPRS to override, so add it.
                if len(urs_rate) == 0:
                    urs['rates'].append(uprs_rate)
                # URS has a rate that the UPRS overrides.
                if len(urs_rate) == 1:
                    urs_rate[0].update(uprs_rate)
                if len(urs_rate) > 1:
                    raise Exception('more than one URS rate matches a UPRS rate')

        # UPRS/URS is overridden and augmented by rates in CPRS

        # for each CPRS rate, find UPRS overidden URS rate and override/augment it
        if 'rates' in cprs:
            for cprs_rate in cprs['rates']:
                # find a matching rate in the URS that was just overidden by UPRS
                urs_uprs_rate = [rate for rate in urs['rates'] if
                        rate['rsi_binding'] == cprs_rate['rsi_binding']]
                # URS/UPRS does not have a rate for the CPRS to override, so add it.
                if len(urs_uprs_rate) == 0:
                    urs['rates'].append(cprs_rate)
                # URS/UPRS has a rate that the CPRS overrides.
                if len(urs_uprs_rate) == 1:
                    urs_uprs_rate[0].update(cprs_rate)
                if len(urs_uprs_rate) > 1:
                    raise Exception('more than one URS/UPRS rate matches a UPRS rate')
    
        # the URS has been thoroughly overridden by the UPRS and CPRS
        return urs

    def load_rate_structure(self, reebill, service):
        '''Returns a RateStructure object representing the combined rate
        structure used to compute charges for the utility bill of the given
        service in 'reebill'.'''
        rs_dict = self._load_combined_rs_dict(reebill, service)
        return RateStructure(rs_dict)

    def load_urs(self, utility_name, rate_structure_name, period_begin=None,
            period_end=None):
        '''Loads Utility (global) Rate Structure document from Mongo, returns
        it as a dictionary.'''
        # TODO: be able to accept a period_begin/period_end for a service and
        # query the URS in a manner ensuring the correct in-effect URS is
        # obtained
        query = {
            "_id.type":"URS",
            "_id.utility_name": utility_name,
            "_id.rate_structure_name": rate_structure_name,
            #"_id.effective": effect<=period_begin,
            #"_id.expires": expires>=period_begin,
        }
        urs = self.collection.find_one(query)
        return urs

    def load_uprss(self, utility_name, rate_structure_name, verbose=False):
        '''Returns list of raw UPRS dictionaries with given utility and rate
        structure name.'''
        cursor = self.collection.find({
            '_id.type': 'UPRS',
            '_id.utility_name': utility_name,
            '_id.rate_structure_name': rate_structure_name
        })
        result = []
        for doc in cursor:
            if doc['_id'].get('effective', None) is None or \
                    doc['_id'].get('expires', None) is None:
                if verbose:
                    print >> sys.stderr, 'malformed UPRS id:', doc['_id']
            else:
                result.append(doc)
        return result

    def load_uprs(self, account, sequence, version, utility_name,
            rate_structure_name):
        '''Loads Utility Periodic Rate Structure docuemnt from Mongo, returns
        it as a dictionary.'''
        # eventually, return a uprs that may have useful information that
        # matches this service period 
        query = {
            "_id.type":"UPRS",
            "_id.account": account,
            "_id.sequence": sequence,
            "_id.version": version,
            "_id.utility_name": utility_name,
            "_id.rate_structure_name": rate_structure_name,
        }
        uprs = self.collection.find_one(query)
        # create it if it does not exist
        # the same behavior should probably be implemented for URS and CPRS so
        # that they can be lazily created
        # TODO 24253017
        if uprs is None:
            uprs = {'rates':[]} 
            uprs = self.save_uprs(account, sequence,
                    version, utility_name, rate_structure_name, uprs)
        return uprs

    def load_cprs(self, account, sequence, version, utility_name,
            rate_structure_name):
        '''Loads Customer Periodic Rate Structure docuemnt from Mongo, returns
        it as a dictionary.'''
        query = {
            "_id.type":"CPRS",
            "_id.account":account, 
            "_id.sequence": int(sequence), 
            "_id.rate_structure_name": rate_structure_name, 
            "_id.utility_name": utility_name, 
            "_id.version":int(version)
        }
        cprs = self.collection.find_one(query)
        if cprs is None:
            raise ValueError('Could not find CPRS: query was %s' % format_query(query))
        return cprs

    def save_rs(self, rate_structure_data):
        '''Easy way to save rate structure without unnecessary arguments.'''
        rate_structure_data = bson_convert(rate_structure_data)
        self.collection.save(rate_structure_data)

    def save_urs(self, utility_name, rate_structure_name, effective, expires,
            rate_structure_data):
        '''Saves the dictionary 'rate_structure_data' as a Utility (global)
        Rate Structure document in Mongo.'''
        rate_structure_data['_id'] = { 
            "type":"URS",
            "utility_name": utility_name,
            "rate_structure_name": rate_structure_name,
        }
        rate_structure_data = bson_convert(rate_structure_data)
        self.collection.save(rate_structure_data)
        return rate_structure_data

    def save_uprs(self, account, sequence, version, utility_name,
            rate_structure_name, rate_structure_data):
        '''Saves the dictionary 'rate_structure_data' as a Utility Periodic
        Rate Structure document in Mongo.'''
        rate_structure_data['_id'] = { 
            "type": "UPRS",
            'account': account,
            'sequence': sequence,
            'version': version,
            "utility_name": utility_name,
            "rate_structure_name": rate_structure_name
        }
        rate_structure_data = bson_convert(rate_structure_data)
        self.collection.save(rate_structure_data)
        return rate_structure_data

    def save_cprs(self, account, sequence, version, utility_name,
            rate_structure_name, rate_structure_data):
        '''Saves the dictionary 'rate_structure_data' as a Customer Periodic
        Rate Structure document in Mongo.'''
        rate_structure_data['_id'] = { 
            'type': 'CPRS',
            'account': account,
            'sequence': int(sequence),
            'version': int(version),
            'utility_name': utility_name,
            'rate_structure_name': rate_structure_name,
        }
        rate_structure_data = bson_convert(rate_structure_data)
        self.collection.save(rate_structure_data)
        return rate_structure_data


class RateStructure(object):
    """ 
    A RateStructure consist of Registers and RateStructureItems. The rate
    structure is the model for how utilities calculate their utility bill.
    This model does not necessarily dictate the reebill, because the reebill
    can have charges that are not part of this model. This is also why the rate
    structure model does not comprehend charge grouping, subtotals or totals.

    A RateStructure stores lots of state.  Reload it for a new uncomputed one.
    """

    # TODO: make sure register descriptor and rate structure item bindings do
    # not collide
    registers = []
    rates = []

    def __init__(self, rs_data):
        """
        Construct with a dictionary that contains the necessary fields for the ratestructure
        including registers and rate structure items.

        This class may be constructed from a URS, UPRS, CPRS or probable rate structure
        """
        # create a Register object from each dictionary in the "registers" part
        # of 'rs_data', and make each of those Registers the value of attribute
        # of this RateStructure, whose name is the "register_binding" in that
        # dictionary.
        self.registers = [Register(reg_data, None, None) for reg_data in rs_data["registers"]]
        for reg in self.registers:
            if reg.register_binding is None:
                raise Exception("Register descriptor required.\n%s" % reg)
            # this is equivalent to "setattr(self, reg.register_binding, reg)"
            self.__dict__[reg.register_binding] = reg

        # RSIs refer to RS namespace to access registers,
        # so they are constructed with self along with their properties
        # so that RSIs have access to this object's namespace and can
        # pass the ratestructure into eval as the global namespace
        #
        # RSI fields like quantity and rate refer to values in other RSIs.
        # so a common namespace must exist for the eval() strategy found in RSIs.
        # Therefore, the RSIs are added to self by RSI Descriptor.
        # RSIs refer to other RSIs by Descriptor.
        # TODO: are self.rates ever referenced? If not, just stick them in self.__dict__

        # do the same thing with RateStructureItems (aka "rates") as with
        # registers above: create a RateStructureItem object from each
        # dictionary in the "rates" part of 'rs_data', and add it as an
        # attribute with the name of its "rsi_binding"
        # (note that register_binding associates registers in a reebill with
        # registers in a RateStructure; rsi_binding associates charges in a
        # reebill with RSIs in a RateStructure)
        self.rates = [RateStructureItem(rsi_data, self) for rsi_data in rs_data["rates"]]
        for rsi in self.rates:
            if rsi.rsi_binding is None:
                raise Exception("RSI descriptor required.\n%s" % rsi)
            self.__dict__[rsi.rsi_binding] = rsi


    def bind_register_readings(self, register_readings):
        '''Takes the list of register dictionaries from a reebill, and for each
        of those, locates a register in this rate structure with the same value
        for the key "register_binding", and copies the value of "quantity" from
        the reebill register dictionary to the rate structure register
        dictionary.'''
        # previous comment:
        # for the register readings that are passed in, bind their 
        # energy value to the register in this rate structure
        # notifying of ones that don't match

        for register_reading in register_readings:
            # find matching descriptor in rate structure
            matched = False
            for register in self.registers:
                if register.register_binding == register_reading['register_binding']:
                    matched = True
                    register.quantity = register_reading['quantity']
                    #print "%s bound to rate structure" % register_reading
            if not matched:
                pass
                #print "%s not bound to rate structure" % register_reading

    def bind_charges(self, charges):
        '''For each charge in a list of charges from a reebill, find the
        corresponding Rate Structure Item (by rsi_binding) and copy the values
        of "description", "quantity", "quantity_units", "rate", and
        "rate_units" from the RSI to the charge.'''
        for charge in charges:
            # get rate structure item binding for this charge
            rsi = self.__dict__[charge['rsi_binding']]

            # copy some fields from the RSI to the charge
            if rsi.description is not None:
                charge['description'] = rsi.description
            if rsi.quantity is not None:
                charge['quantity'] = rsi.quantity
            if rsi.quantity_units is not None:
                charge['quantity_units'] = rsi.quantity_units
            if rsi.rate is not None:
                charge['rate'] = rsi.rate
            if rsi.rate_units is not None:
                charge['rate_units'] = rsi.rate_units
            charge['total'] = rsi.total

            rsi.bound = True

        for rsi in self.rates:
            if (hasattr(rsi, 'bound') == False):
                #print "RSI was not bound " + str(rsi)
                pass

    def __str__(self):
        s = '' 
        for reg in self.registers:
            s += str(reg)
        s += '\n'
        for rsi in self.rates:
            s += str(rsi)
        return s


class Register(object):
    '''Wrapper for a register dictionary/mongo document inside meter inside
    utility bill document.'''

    def __init__(self, reg_data, prior_read_date, present_read_date):
        if 'quantity' not in reg_data:
            raise Exception("Register must have a reading")
        if not reg_data['quantity']:
            raise Exception("Register must have a quantity")

        # copy pairs of the form (key, value) in 'reg_data' to pairs of the
        # form (_key, value) via the property decorators below
        for key in reg_data:
            setattr(self, key, reg_data[key])
        # prior_read_date & present_read_date are properties of meters in
        # mongo, so they're not in the 'reg_data' dict, which comes from the
        # register subdocument.
        self.prior_read_date = prior_read_date
        self.present_read_date = present_read_date

        # only TOU registers have inclusions and exclusions in their mongo
        # document. if these are absent, this is not a TOU register, but
        # 'inclusions' and 'exclusions' are necessary for accumulating
        # renewable energy consumption in a shadow register, so we set them to
        # cover the entire day
        if not 'inclusions' in reg_data:
            self.inclusions = [{'fromhour': 0, 'tohour': 23, 'weekday':[1,2,3,4,5,6,7]}]
            self.exclusions = []

    @property
    def register_binding(self):
        return self._register_binding
    @register_binding.setter
    def register_binding(self, value):
        self._register_binding = value

    @property
    def description(self):
        return self._description
    @description.setter
    def description(self, value):
        self._description = value

    @property
    def quantity(self):
        return self._quantity
    @quantity.setter
    def quantity(self, value):
        # have to express value as float so that expressions can eval()
        self._quantity = float(value)

    @property
    def quantity_units(self):
        return self._quantity_units
    @quantity_units.setter
    def quantity_units(self, value):
        self._quantity_units = value
    
    @property
    def prior_read_date(self):
        return self._prior_read_date
    @prior_read_date.setter
    def prior_read_date(self, value):
        self._prior_read_date = value
    
    @property
    def present_read_date(self):
        return self._present_read_date
    @present_read_date.setter
    def present_read_date(self, value):
        self._present_read_date = value

    @property
    def identifier(self):
        return self._identifier
    @identifier.setter
    def identifier(self, value):
        self._identifier = value

    def __str__(self):
        return "Register %s: %s, %s, %s" % (
            self.register_binding if self.register_binding else 'No Descriptor',
            self.description if self.description else 'No Description',
            self.quantity if self.quantity else 'No Reading',
            self.quantity_units if self.quantity_units else 'No Quantity Units',
        )


class RateStructureItem(object):
    """ Container class for RSIs.  This serves as a class from which RateStructureItem instances are obtained
    via definition in the rs data. An RSI consists of (importantly) a descriptor, quantity, rate and total.
    The descriptor must be set and map to the bill rsibinding for a given charge.
    The quantity may be a number or a python expression, usually the variable of a register in the rate_structure.
    In cases where these RateStructureItem attributes are absent, the rate_structure_item can
    calculate them.  A notable example is total, which is usually not set in the rs data except for
    fixed charges, like a customer charge. 
    RSIs track their values as instance variables that match the properties but prepended with an underscore.
    RSIs internally represent the properties as strings, but externally return the type from the eval(expr)
    operation.
    """

    # allow printing this object to evaluate the rate structure properties
    # __str__ seems to bury exceptions, so not necessary the best thing 
    # to have enabled during development.
    #TODO: better name
    deepprint = True

    # set by the ratestructure that contains the rate_structure_items
    # so each RSI can refer to its parent RS
    _rate_structure = None

    def __init__(self, props, rate_structure):
        """
        Instantiate an RSI with a dictionary of RSI properties that come from the 'rates:'
        used to instantiate the parent RateStructure.
        The allowed types for the values of an RSI property are those that are python native: str, float or int.
        """
        self._rate_structure = rate_structure
        for key in props:
            # all keys passed are prepended with an _
            # and directly set in this instance
            # because we cover these RSI instance attributes 
            # with an @property decorator to encapsulate
            # functionality required to dynamically 
            # evaluate those attributes and return the results of eval()

            # if a value exists in the rate
            # TODO:22974637 check for key membership using key in dict statement
            value = props[key]
            # if not None, and is a string with contents
            if (value is not None):
                 
                # values are initially set as strings, and as the values are evaluated
                # the return type is a function of what the expression evals to.
                value = str(value)

                if len(value):
                    # place these propery values in self, but prepend the _ so @property methods of self
                    # do not access them since @property methods are used for expression evaluation
                    setattr(self, "_"+key, value)
                else:
                    pass
                    #print "Warning: %s %s is an empty property" % (props["rsi_binding"], key)
            else:
                pass
                #print "Warning: %s %s is an empty property" % (props["rsi_binding"], key)
                # Don't add the attr the property since it has no value and its only contribution 
                # would be to make for None type checking all over the place.

        self.evaluated_total = False
        self.evaluated_quantity = False
        self.evaluated_rate = False

    @property
    def rsi_binding(self):
        if hasattr(self, "_rsi_binding"):
            return self._rsi_binding
        else:
            return None

    def evaluate(self, rsi_value):
        """An RSI value is an str that has an expression that may be evaluated. An
        RSI expression can be as simple as a number, or as complex as a Python
        statement that references values of other RSIs.

        Knowing the behavior of eval() is important to understand this
        implementation. eval() returns a type that is a function of the
        expression passed into it. Much of the time, there is a floating point
        number in an expression. Consequently, RSI and Registers have to
        typically return a 'float' for numerical values so that eval() can
        avoid type mismatches when using +,-,/ and * operators. """
        assert isinstance(rsi_value, basestring)

        try:
            # eval results in a recursive evaluation of all referenced expressions
            # eval evals rsi_value in the context of self._rate_structure.__dict__
            # this enables the rsi_value to contain references to attributes 
            # (registers and RSIs) that are held in the RateStructure
            result = eval(rsi_value, self._rate_structure.__dict__)
            # an evaluated result can be a string or float or who knows what
            return result

        except RuntimeError as re:
            # TODO: set RSI state to track recursion.
            raise RecursionError(self.rsi_binding, rsi_value)

        # RSIs raise this if the requested property does not exist in yaml
        except NoPropertyError as npe:
            raise npe

        # Raised when recursion occurs in an expression passed into above eval
        except RecursionError as re:
            raise re

        except NameError as ne:
            raise NoSuchRSIError(self.rsi_binding, rsi_value)

        except SyntaxError as se:
            raise BadExpressionError(self.rsi_binding, rsi_value)

        except Exception as e:
            print "Unexpected Exception %s %s" % (str(type(e)),str(e))
            print "Handle it gracefully"
            raise e

    @property
    def total(self):
        if self.evaluated_total is False:
            if hasattr(self, "_total"):
                self._total = self.evaluate(self._total)
                self.evaluated_total = True
                return self._total

            # total isn't defined by RSI, so it must be computed
            else:

                # total must be computed from rate and/or quantity.

                # TODO: consider the meaning of the possible existing rate and quantity for the RSI
                # even though it has a total.  What if r and q are set and don't equal a total that has been set?!

                # TODO: it total exists, and either rate or quantity is missing, why not solve for
                # the missing term?

                # quantities or rates may be a string or float due to eval()
                q = self.quantity
                r = self.rate
                t = Decimal(str(q)) * Decimal(str(r))

                # perform decimal round rule. 
                rule = self._roundrule if hasattr(self, "_roundrule") else None
                t = Decimal(t).quantize(Decimal('.00'), rule)

                # An evaluated value in an RSI must be returned as a float. Why?
                # Because it is used as a term in expressions that are passed into
                # eval().  And, eval cannot do things like divide by a string.
                # e.g. PER_THERM_RATE, rate Value: 8.31 / REG_THERMS.quantity
                self._total = float(t)
                self.evaluated_total = True
                return self._total

        else:
            return self._total

    @property
    def description(self):
        if hasattr(self, "_description"):
            return self._description
        else:
            return None

    @property
    def quantity(self):

        if self.evaluated_quantity is False:
            if hasattr(self, "_quantity"):
                self._quantity = float(self.evaluate(self._quantity))
                self.evaluated_quantity = True
                return self._quantity
            else:
                # no quantity attribute? It may be assumed to be one
                self._quantity = float("1")
                self.evaluated_quantity = True
                return self._quantity

            raise NoPropertyError(self._rsi_binding, "%s.quantity does not exist" % self._rsi_binding)
        else:
            return float(self._quantity)

    @property
    def quantity_units(self):
        if hasattr(self, "_quantity_units"):
            return self._quantity_units
        else:
            return None

    @property
    def rate(self):

        if self.evaluated_rate is False:
            if hasattr(self, "_rate"):
                self._rate = float(self.evaluate(self._rate))
                self.evaluated_rate = True
                return self._rate

            raise NoPropertyError(self._rsi_binding, "%s.rate does not exist" % self._rsi_binding)
        else:
            return float(self._rate)

    @property
    def rate_units(self):
        return self._rate_units if hasattr(self, "_rate_units") else None

    @property
    def roundrule(self):
        return self._roundrule if hasattr(self, "_roundrule") else None

    def __str__(self):
        s = 'Unevaluated RSI\n'
        s += 'rsi_binding: %s\n' % (self._rsi_binding if hasattr(self, '_rsi_binding') else '')
        s += 'description: %s\n' % (self._description if hasattr(self, '_description') else '')
        s += 'quantity: %s\n' % (self._quantity if hasattr(self, '_quantity') else '')
        s += 'quantity_units: %s\n' % (self._quantity_units if hasattr(self, '_quantity_units') else '')
        s += 'rate: %s\n' % (self._rate if hasattr(self, '_rate') else '')
        s += 'rate_units: %s\n' % (self._rate_units if hasattr(self, '_rate_units') else '')
        s += 'roundrule: %s\n' % (self._roundrule if hasattr(self, '_roundrule') else '')
        s += 'total: %s\n' % (self._total if hasattr(self, '_total') else '')
        s += '\n'
        if self.deepprint is True:
            s += 'Evaluated RSI\n'
            s += 'rsi_binding: %s\n' % (self.rsi_binding)
            s += 'description: %s\n' % (self.description)
            s += 'quantity: %s\n' % (self.quantity)
            s += 'quantity_units: %s\n' % (self.quantity_units)
            s += 'rate: %s\n' % (self.rate)
            s += 'rate_units: %s\n' % (self.rate_units)
            s += 'roundrule: %s\n' % (self.roundrule)
            s += 'total: %s\n' % (self.total)
            s += '\n'
        return s

if __name__ == '__main__':
    # example of probable rate structure
    dao = RateStructureDAO(**{
        'database': 'skyline-dev',
        'collection': 'ratestructure',
        'host': 'localhost',
        'port': 27017
    })
    from pprint import PrettyPrinter
    probable_uprs = dao._get_probable_rsis('washgas', 'DC Non Residential Non Heat', (date(2012,10,1), date(2012,11,1)))
    PrettyPrinter().pprint(probable_uprs)

