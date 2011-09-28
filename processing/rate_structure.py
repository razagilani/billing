#!/usr/bin/python
import sys
import yaml
import jinja2
import os
from decimal import Decimal
import traceback
import inspect
import copy

import pymongo
import uuid

from billing import mongo
import yaml

import pprint
pp = pprint.PrettyPrinter(indent=1)

class RateStructureDAO():
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

    def __init__(self, config):

        self.config = config
        self.connection = None
        self.database = None
        self.collection = None

        try:
            self.connection = pymongo.Connection(self.config['host'], int(self.config['port']))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        
        self.database = self.connection[self.config['database']]
        self.collection = self.database[self.config['collection']]

    def __del__(self):
        # TODO: clean up mongo resources here?
        pass

    def load_probable_rs(self, reebill, service):

        # return a probable rate structure for each utilbill in the reebill

        # all the data needed to identify a probable rate structure
        account = reebill.account
        sequence = reebill.sequence
        branch = reebill.branch
        rsbinding = reebill.rate_structure_name_for_service(service)
        utility_name = reebill.utility_name_for_service(service)
        rate_structure_name = reebill.rate_structure_name_for_service(service)
        (period_begin, period_end) = reebill.utilbill_period_for_service(service)


        # load the URS
        urs = self.load_urs(utility_name, rate_structure_name, period_begin, period_end)
        if urs is None: raise Exception("Could not lookup URS")

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
        del urs['_id']

        # remove uuids because they are not used in rate structure computation
        for urs_rate in urs['rates']:
            del urs_rate['uuid']

        for urs_reg in urs['registers']:
            del urs_reg['uuid']

        # load the UPRS
        uprs = self.load_uprs(utility_name, rate_structure_name, period_begin, period_end)

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
        del uprs['_id']

        # remove the uuids because they are not used in rate structure computation
        if 'rates' in uprs:
            for uprs_rate in uprs['rates']:
                del uprs_rate['uuid']

        # load the CPRS
        cprs = self.load_cprs(account, sequence, branch, utility_name, rate_structure_name)

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
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
                urs_rate = [rate for rate in urs['rates'] if rate['descriptor'] == uprs_rate['descriptor']]
                # URS does not have a rate for UPRS to override, so add it.
                if len(urs_rate) == 0:
                    urs['rates'].append(uprs_rate)
                # URS has a rate that the UPRS overrides.
                if len(urs_rate) == 1:
                    urs_rate[0].update(uprs_rate)
                if len(urs_rate) > 1: raise Exception('more than one URS rate matches a UPRS rate')


        # UPRS/URS is overridden and augmented by rates in CPRS

        # for each CPRS rate, find UPRS overidden URS rate and override/augment it
        if 'rates' in cprs:
            for cprs_rate in cprs['rates']:
                # find a matching rate in the URS that was just overidden by UPRS
                urs_uprs_rate = [rate for rate in urs['rates'] if rate['rsi_binding'] == cprs_rate['rsi_binding']]
                # URS/UPRS does not have a rate for the CPRS to override, so add it.
                if len(urs_uprs_rate) == 0:
                    urs['rates'].append(cprs_rate)
                # URS/UPRS has a rate that the CPRS overrides.
                if len(urs_uprs_rate) == 1:
                    urs_uprs_rate[0].update(cprs_rate)
                if len(urs_uprs_rate) > 1: raise Exception('more than one URS/UPRS rate matches a UPRS rate')
    
        # the URS has been thoroughly overridden by the UPRS and CPRS
        return urs

    # Now only used to convert YAML to Mongo
    def load_rs(self, reebill, service):

        account = reebill.account
        sequence = reebill.sequence
        branch = reebill.branch
        utility_name = reebill.utility_name_for_service(service)

        rate_structure = yaml.load(file(os.path.join(self.config["rspath"], str(utility_name), str(account), str(sequence)+".yaml")))

        rate_structure_name = rate_structure['name']

        # if there is no cprs, assume the rs hasn't been converted and convert it  
        # to both a URS and CPRS
        if self.load_cprs(account, sequence, branch, utility_name, rate_structure_name) is None:

            #
            # convert rs.yaml to URS 
            #

            # copy it so rate_structure yaml is preserved and can be returned to old style code
            convert_rs = copy.deepcopy(rate_structure)
            for rate in convert_rs['rates']:
                if 'descriptor' not in rate: raise Exception('A descriptor is necessary')
                rate['rsi_binding'] = rate['descriptor']
                del rate['descriptor']
                # add a uuid so it can be edited in UI
                rate['uuid'] = str(uuid.uuid1())
                if 'rate' in rate: 
                    rate['rate'] = str(rate['rate'])
                if 'rateunits' in rate: 
                    rate['rate_units'] = str(rate['rateunits'])
                    del rate['rateunits']
                if 'quantityunits' in rate:
                    rate['quantity_units'] = str(rate['quantityunits'])
                    del rate['quantityunits']

            for reg in convert_rs['registers']:
                reg['uuid'] = str(uuid.uuid1())
                reg['quantity'] = str(reg['quantity'])
                reg['quantity_units'] = str(reg['quantityunits'])
                reg['register_binding'] = str(reg['descriptor'])
                del reg['descriptor']

            # might need to keep these in document body, since it won't be possible
            # for a reebill to directly query by effective and expires.  Maybe
            # period begin and end is good enough to find the URS.
            if 'name' in convert_rs: del convert_rs['name']
            if 'service' in convert_rs: del convert_rs['service']
            if 'effective' in convert_rs: 
                effective = convert_rs['effective']
                del convert_rs['effective']
            if 'expires'in convert_rs: 
                expires = convert_rs['expires']
                del convert_rs['expires']

            # will overwrite for every CPRS but last write becomes URS on cut-over
            self.save_urs(utility_name, rate_structure_name, effective, expires, convert_rs)

            #
            # don't worry about the UPRS until there is UI support to form it
            #

            #
            # convert rs.yaml to CPRS
            #
            convert_rs = copy.deepcopy(rate_structure)
            for rate in convert_rs['rates']:
                # Assume these have gone into URS
                if 'description' in rate: del rate['description']
                rate['uuid'] = str(uuid.uuid1())
                rate['rate'] = str(rate['rate'])
                if 'rateunits' in rate: 
                    rate['rate_units'] = str(rate['rateunits'])
                    del rate['rateunits']
                if 'quantityunits' in rate:
                    rate['quantity_units'] = str(rate['quantityunits'])
                    del rate['quantityunits']
                rate['quantity'] = str(rate['quantity'])
                rate['rsi_binding'] = rate['descriptor']
                del rate['descriptor']

            # remove regs  and things not needed in the CPRS
            if 'effective' in convert_rs: del convert_rs['effective']
            if 'expires' in convert_rs: del convert_rs['expires']
            if 'registers' in convert_rs: del convert_rs['registers']
            if 'name' in convert_rs: del convert_rs['name']
            if 'service' in convert_rs: del convert_rs['service']

            self.save_cprs(account, sequence, branch, utility_name, rate_structure_name, convert_rs)

            rate_structure = self.load_cprs(account, sequence, branch, utility_name, rate_structure_name)

        # return the yaml so things still work
        return rate_structure

    def load_rate_structure(self, reebill, service):
        '''
        Return a RateStructure that acts on URS/UPRS/CPRS combined rate structure
        '''

        # CONVERTS FROM YAML TO MONGO
        # create one in mongo from YAML
        self.load_rs(reebill, service)

        rs_data = self.load_probable_rs(reebill, service)

        return RateStructure(rs_data)

    # TODO: consider just accepting a reebill
    def load_urs(self, utility_name, rate_structure_name, period_begin=None, period_end=None):

        # TODO: be able to accept a period_begin/period_end for a service and query 
        # the URS in a manner ensuring the correct in-effect URS is obtained

        query = {
            "_id.type":"URS",
            "_id.utility_name": utility_name,
            "_id.rate_structure_name": rate_structure_name,
            #"_id.effective": effect<=period_begin,
            #"_id.expires": expires>=period_begin,

        }
        urs = self.collection.find_one(query)

        return urs

    # TODO: consider just accepting a reebill
    def load_uprs(self, utility_name, rate_structure_name, begin_period, end_period):

        # eventually, return a uprs that may have useful information that matches this service period 
        uprs = {'_id': None}

        return uprs

    # TODO: consider just accepting a reebill
    def load_cprs(self, account, sequence, branch, utility_name, rate_structure_name):
        # TODO param types

        query = {
            "_id.type":"CPRS",
            "_id.account":account, 
            "_id.sequence": int(sequence), 
            "_id.rate_structure_name": rate_structure_name, 
            "_id.utility_name": utility_name, 
            "_id.branch":int(branch)}


        cprs = self.collection.find_one(query)

        return cprs

    def save_urs(self, utility_name, rate_structure_name, effective, expires, rate_structure_data):

        rate_structure_data['_id'] = { 
            "type":"URS",
            "utility_name": utility_name,
            "rate_structure_name": rate_structure_name,
            # TODO: support date ranges for URS
            #'effective': effective,
            #'expires': expires
        }


        # TODO: bson_convert has to become a util function
        rate_structure_data = mongo.bson_convert(rate_structure_data)

        self.collection.save(rate_structure_data)

    def save_cprs(self, account, sequence, branch, utility_name, rate_structure_name, rate_structure_data):

        rate_structure_data['_id'] = { 
            'type': 'CPRS',
            'account': account,
            'sequence': int(sequence),
            'branch': int(branch),
            'utility_name': utility_name,
            'rate_structure_name': rate_structure_name,
        }


        # TODO: bson_convert has to become a util function
        rate_structure_data = mongo.bson_convert(rate_structure_data)

        self.collection.save(rate_structure_data)

    def save_rs(self, account, sequence, rsbinding, rate_structure):

        yaml.safe_dump(rate_structure, open(os.path.join(self.config["rspath"], rsbinding, account, sequence+".yaml"), "w"), default_flow_style=False)



class RateStructure():
    """ 
    A RateStructure consist of Registers and RateStructureItems.
    The rate structure is the model for how utilities calculate their utility bill.  This model does not
    necessarily dictate the reebill, because the reebill can have charges that are not part of this model.
    This is also why the rate structure model does not comprehend charge grouping, subtotals or totals.

    A RateStructure stores lots of state.  Reload it for a new uncomputed one.
    """

    # TODO: make sure register descriptor and rate structure item bindings do not collide

    registers = []
    rates = []

    def __init__(self, rs_data):
        """
        Construct with a dictionary that contains the necessary fields for the ratestructure
        including registers and rate structure items.

        This class may be constructed from a URS, UPRS, CPRS or probable rate structure
        """

        self.registers = [Register(reg_data, None, None) for reg_data in rs_data["registers"]]
        for reg in self.registers:
            if reg.register_binding is None:
                raise Exception("Register descriptor required.\n%s" % reg)
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

        self.rates = [RateStructureItem(rsi_data, self) for rsi_data in rs_data["rates"]]
        for rsi in self.rates:
            if rsi.rsi_binding is None:
                raise Exception("RSI descriptor required.\n%s" % rsi)
            self.__dict__[rsi.rsi_binding] = rsi


    def register_needs(self):
        """ 
        Return a list of registers that must be populated with energy.
        """
        needs = []
        for register in self.registers:
            needs.append(register)
        return needs

    def bind_register_readings(self, register_readings):

        # for the register readings that are passed in, bind their 
        # energy value to the register in this rate structure
        # notifying of ones that don't match

        for register_reading in register_readings:
            # find matching descriptor in rate structure
            matched = False
            for register_need in self.registers:
                if register_need.register_binding == register_reading['register_binding']:
                    matched = True
                    register_need.quantity = register_reading['quantity']
                    #print "%s bound to rate structure" % register_reading
            if not matched:
                print "%s not bound to rate structure" % register_reading

    def bind_charges(self, charges):

        # for each list of charges passed in, get the charge rsi_binding
        # and apply its values to the rate structure, or override its
        # values.

        for charge in charges:
            rsi = self.__dict__[charge['rsi_binding']]

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
    def __init__(self, reg_data, prior_read_date, present_read_date):
        if 'quantity' not in reg_data:
            raise Exception("Register must have a reading")
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

    def valid_hours(self, theDate):
        return [(0, 23)]
        # no idea what this code does--what is inclusion[3]?
        """For a given date, return a list of tuples that describe the ranges of hours 
        this register should accumulate energy
        e.g. [(8,12), (15,19)] == 8:00:00AM to 11:59:59, and 3:00:00pm to 6:59:59
        Taken from fetch_bill_data.Register."""
        '''
        hour_tups = []
        for inclusion in self.inclusions:
            # if theDate matches a holiday listed as an inclusion, meter is on the entire day.
            # Full day in inclusion (holiday) override weekday rules
            if theDate in inclusion[3]:
                return [(0, 23)]
            if theDate.isoweekday() in inclusion[2]:
                # weekday matches, make sure it is not excluded due to full day in exclusion (holiday)
                for exclusion in self.exclusions:
                    if (theDate in exclusion[3]):
                        return []
                hour_tups.append((inclusion[0], inclusion[1]))
        '''
        return hour_tups

    def __str__(self):

        return "Register %s: %s, %s, %s" % (
            self.register_binding if self.register_binding else 'No Descriptor',
            self.description if self.description else 'No Description',
            self.quantity if self.quantity else 'No Reading',
            self.quantity_units if self.quantity_units else 'No Quantity Units',
        )

class RateStructureItem():

    """ 
    Container class for RSIs.  This serves as a class from which RateStructureItem instances are obtained
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
                    print "Warning: %s %s is an empty property" % (props["descriptor"], key)
            else:
                print "Warning: %s %s is an empty property" % (props["descriptor"], key)
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
        """
        An RSI value is an str that has an expression that may be evaluated.
        An RSI expression can be as simple as a number, or as complex as a Python
        statement that references values of other RSIs.

        Knowing the behavior of eval() is important to understand this implementation.
        eval() returns a type that is a function of the expression passed into it.
        Much of the time, there is a floating point number in an expression.
        Consequently, RSI and Registers have to typically return a 'float' for numerical
        values so that eval() can avoid type mismatches when using +,-,/ and * operators.
        """
        assert type(rsi_value) is str

        caller = inspect.stack()[1][3]
        #print "RSI Evaluate: %s, %s Value: %s" % (self._rsi_binding, caller, rsi_value)

        try:

            # eval results in a recursive evaluation of all referenced expressions
            # eval evals rsi_value in the context of self._rate_structure.__dict__
            # this enables the rsi_value to contain references to attributes 
            # (registers and RSIs) that are held in the RateStructure
            result = eval(rsi_value, self._rate_structure.__dict__)
            #print "RSI Evaluate Result: %s %s" % (type(result), result)

            # an evaluated result can be a string or float or who knows what
            return result

        except RuntimeError as re:

            # TODO: set RSI state to track recursion.
            raise RecursionError(self.descriptor, rsi_value)

        # RSIs raise this if the requested property does not exist in yaml
        except NoPropertyError as npe:
            raise npe

        # Raised when recursion occurs in an expression passed into above eval
        except RecursionError as re:
            raise re

        except NameError as ne:
            raise NoSuchRSIError(self.descriptor, rsi_value)

        except SyntaxError as se:
            raise BadExpressionError(self.descriptor, rsi_value)

        except Exception as e:
            print "Unexpected Exception %s %s" % (str(type(e)),str(e))
            print "Handle it gracefully"
            raise e

    @property
    def total(self):
        """
        """
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
class RSIError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, descriptor, msg):
        self.descriptor = descriptor
        self.msg = msg
    def __str__(self):
        return "%s %s" % (self.descriptor, self.msg)

class RecursionError(RSIError):
    pass

class NoPropertyError(RSIError):
    pass

class NoSuchRSIError(RSIError):
    pass

class BadExpressionError(RSIError):
    pass



