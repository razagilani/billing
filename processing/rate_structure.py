#!/usr/bin/python
import sys
import yaml
import jinja2
import os
from decimal import Decimal
import traceback
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

        # remove the order and uuids because they are not used in rate structure computation
        for urs_rate in urs['rates']:
            del urs_rate['uuid']
            del urs_rate['order']

        for urs_reg in urs['registers']:
            del urs_reg['uuid']
            del urs_reg['order']

        # load the UPRS
        uprs = self.load_uprs(utility_name, rate_structure_name, period_begin, period_end)

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
        del uprs['_id']

        # remove the order and uuids because they are not used in rate structure computation
        if 'rates' in uprs:
            for uprs_rate in uprs['rates']:
                del uprs_rate['uuid']
                del uprs_rate['order']

        # load the CPRS
        cprs = self.load_cprs(account, sequence, branch, utility_name, rate_structure_name)

        # remove the mongo key, because the requester already has this information
        # and we do not want application code depending on the "_id" field.
        del cprs['_id']

        # remove the order and uuids because they are not used in rate structure computation
        if 'rates' in cprs:
            for cprs_rate in cprs['rates']:
                del cprs_rate['uuid']
                del cprs_rate['order']


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
                urs_uprs_rate = [rate for rate in urs['rates'] if rate['descriptor'] == cprs_rate['descriptor']]
                # URS/UPRS does not have a rate for the CPRS to override, so add it.
                if len(urs_uprs_rate) == 0:
                    urs['rates'].append(cprs_rate)
                # URS/UPRS has a rate that the CPRS overrides.
                if len(urs_uprs_rate) == 1:
                    urs_uprs_rate[0].update(cprs_rate)
                if len(urs_uprs_rate) > 1: raise Exception('more than one URS/UPRS rate matches a UPRS rate')
    
        # the URS has been thoroughly overridden by the UPRS and CPRS
        return urs

    # TODO this is load_rs_data
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
            order = 0
            for rate in convert_rs['rates']:
                if 'descriptor' not in rate: raise Exception('A descriptor is necessary')
                # assume that quantity would never be in URS?
                if 'quantity' in rate: del rate['quantity']
                # add a uuid so it can be edited in UI
                rate['uuid'] = str(uuid.uuid1())
                rate['order'] = order
                order += 1

            order = 0
            for reg in convert_rs['registers']:
                reg['uuid'] = str(uuid.uuid1())
                reg['order'] = order
                order += 1


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
            order = 0
            for rate in convert_rs['rates']:
                # Assume these have gone into URS
                if 'description' in rate: del rate['description']
                if 'rateunits' in rate: del rate['rateunits']
                if 'quantityunits' in rate: del rate['quantityunits']
                rate['uuid'] = str(uuid.uuid1())
                rate['order'] = order
                order += 1

            # remove regs  and things not needed in the CPRS
            if 'effective' in convert_rs: del convert_rs['effective']
            if 'expires' in convert_rs: del convert_rs['expires']
            if 'registers' in convert_rs: del convert_rs['registers']
            if 'name' in convert_rs: del convert_rs['name']
            if 'service' in convert_rs: del convert_rs['service']

            self.save_cprs(account, sequence, branch, utility_name, rate_structure_name, convert_rs)

        # return the yaml so things still work
        return rate_structure

    def load_rate_structure(self, reebill, service):
        '''
        Return a RateStructure that acts on rate structure from mongo
        '''

        # create on in mongo from YAML
        self.load_rs(reebill, service)

        rs_data = self.load_probable_rs(reebill, service)

        return RateStructureNew(rs_data)

    def load_urs(self, utility_name, rate_structure_name, period_begin, period_end):

        # TODO: be able to accept a period_begin/period_end for a service and query 
        # the URS in a manner ensuring the correct in-effect URS is obtained

        query = {
            '_id.utility_name': utility_name,
            '_id.rate_structure_name': rate_structure_name,
            #'_id.effective': effect<=period_begin,
            #'_id.expires': expires>=period_begin,

        }
        urs_rate_structure = self.collection.find_one(query)
        #{
        #    '_id': {
        #        'utility_name': utility_name,
        #        'rate_structure_name': rate_structure_name,
        #        #'effective':  effect<=period_begin
        #        #'expires': expires>=period_end
        #    }
        #})

        return urs_rate_structure

    def load_uprs(self, utility_name, rate_structure_name, begin_period, end_period):

        # eventually, return a uprs that may have useful information that matches this service period 
        return {'_id':None}

    def load_cprs(self, account, sequence, branch, utility_name, rate_structure_name):
        # TODO param types

        query = {
            "_id.account":account, 
            "_id.sequence": int(sequence), 
            "_id.rate_structure_name": rate_structure_name, 
            "_id.utility_name": utility_name, 
            "_id.branch":int(branch)}

        cprs_rate_structure = self.collection.find_one(query)

        return cprs_rate_structure

    def save_urs(self, utility_name, rate_structure_name, effective, expires, rate_structure_data):

        rate_structure_data['_id'] = { 
            'utility_name': utility_name,
            'rate_structure_name': rate_structure_name,
            # TODO: support date ranges for URS
            #'effective': effective,
            #'expires': expires
        }


        # TODO: bson_convert has to become a util function
        rate_structure_data = mongo.bson_convert(rate_structure_data)

        self.collection.save(rate_structure_data)

    def save_cprs(self, account, sequence, branch, utility_name, rate_structure_name, rate_structure_data):

        rate_structure_data['_id'] = { 
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
        #self.save_rs_mongo(account, sequence, rsbinding, 0, rate_structure)


class RateStructureNew():
    """ 
    A RateStructure consist of Registers and RateStructureItems.
    The rate structure is the model for how utilities calculate their utility bill.  This model does not
    necessarily dictate the reebill, because the reebill can have charges that are not part of this model.
    This is also why the rate structure model does not comprehend charge grouping, subtotals or totals.
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

        self.registers = [RegisterNew(reg_data) for reg_data in rs_data["registers"]]
        for reg in self.registers:
            if reg.descriptor is None:
                raise Exception("Register descriptor required.\n%s" % reg)
            self.__dict__[reg.descriptor] = reg

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

        self.rates = [RateStructureItemNew(rsi_data, self) for rsi_data in rs_data["rates"]]
        for rsi in self.rates:
            if rsi.descriptor is None:
                raise Exception("RSI descriptor required.\n%s" % rsi)
            self.__dict__[rsi.descriptor] = rsi


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
                if register_need.descriptor == register_reading['rsi_binding']:
                    matched = True
                    register_need.quantity = register_reading['total']
                    print "%s bound to rate structure" % register_reading
            if not matched:
                print "%s not bound to rate structure" % register_reading

    def bind_charges(self, charges):

        # for each list of charges passed in, get the charge rsi_binding
        # and apply its values to the rate structure, or override its
        # values.

        for charge in charges:
            rsi = self.__dict__[charge['rsi_binding']]
            print "matched rsi %s to charge %s" % (rsi, charge)

            if rsi.description is not None:
                charge['description'] = rsi.description

            if rsi.quantity is not None:
                charge['quantity'] = rsi.quantity

            if rsi.quantityunits is not None:
                charge['quantity_units'] = rsi.quantityunits

            if rsi.rate is not None:
                charge['rate'] = rsi.rate

            if rsi.rateunits is not None:
                charge['rate_units'] = rsi.rateunits

            charge['total'] = rsi.total

            rsi.bound = True

        for rsi in self.rates:
            if (hasattr(rsi, 'bound') == False):
                print "RSI was not bound " + str(rsi)

                    

    def __str__(self):

        s = '' 
        for reg in self.registers:
            s += str(reg)
        s += '\n'
        for rsi in self.rates:
            s += str(rsi)
        return s

class RateStructure():
    """ 
    A RateStructure consist of Registers and RateStructureItems.
    The rate structure is the model for how utilities calculate their utility bill.  This model does not
    necessarily dictate the re bill, because the re bill can have charges that are not part of this model.
    This is also why the rate structure model does not comprehend charge grouping, subtotals or totals.
    """

    registers = []
    rates = []

    def __init__(self, rs_yaml):
        """
        Construct with a loaded yaml file that contains the necessary fields for the ratestructure
        including registers and rate structure items.
        """

        # Create object tree based on input yaml
        # Note: RSIs convert all yaml types to strings
        self.__bind_yaml(rs_yaml)

        # add Registers to self's namespace
        self.__bind_ns_registers()

        # add RSIs to self's namespace
        self.__bind_ns_rsis()


    def __bind_ns_registers(self):

        # so that registers may be referenced from this objects namespace
        for reg in self.registers:
            if reg.descriptor is None:
                print "Register descriptor required.\n%s" % reg
                continue
            self.__dict__[reg.descriptor] = reg

    def __bind_ns_rsis(self):

        # RSI fields like quantity and rate refer to values in other RSIs.
        # so a common namespace must exist for the eval() strategy found in RSIs.
        # Therefore, the RSIs are added to self by RSI Descriptor.
        # RSIs refer to other RSIs by Descriptor.
        for rsi in self.rates:
            if rsi.descriptor is None:
                print "RSI descriptor required.\n%s" % rsi
                continue

            #print "Got rsi.descriptor %s for rsi %s" % (rsi.descriptor, rsi)
            self.__dict__[rsi.descriptor] = rsi

    def __bind_yaml(self, rs_yaml):

        #TODO: graceful failure on bad yaml
        self.name = rs_yaml["name"]
        self.service = rs_yaml["service"]
        if rs_yaml["registers"] is not None:
            self.registers = [Register(reg_rs_yaml) for reg_rs_yaml in rs_yaml["registers"]]

        # RSIs refer to RS namespace, so they are constructed with self along with their properties
        # so that RSIs have access to this object's namespace and can
        # pass the ratestructure into eval as the global namespace
        if rs_yaml["rates"] is not None: 
            self.rates = [RateStructureItem(rsi_rs_yaml, self) for rsi_rs_yaml in rs_yaml["rates"]]

    def register_needs(self):
        """ 
        Return a list of registers that must be populated with energy.
        A Register may have its value set in the yaml file.
        """
        needs = []
        for register in self.registers:
            if (register.quantity == None):
                needs.append(register)
        return needs

    def __str__(self):

        s = '' 
        s += '%s\t' % (self.name if hasattr(self, 'name') else '')
        s += '%s\t' % (self.service if hasattr(self, 'service') else '')
        s += '\n'
        for reg in self.registers:
            s += str(reg)
        for rsi in self.rates:
            s += str(rsi)
        return s


class Register():

    def __init__(self, props):
            for key in props:
                setattr(self, key, props[key])

    #TODO: implement @properties for registers

    def __str__(self):

        s = '' 
        s += '%s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += '%s\t' % (self.description if hasattr(self, 'description') else '')
        s += '%s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += '%s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += '\n'
        return s

class RegisterNew():

    def __init__(self, props):
            for key in props:
                setattr(self, key, props[key])

    #TODO: implement @properties for registers

    def __str__(self):

        s = '' 
        s += '%s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += '%s\t' % (self.description if hasattr(self, 'description') else '')
        s += '%s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += '%s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += '\n'
        return s


class RateStructureItem():
    """ 
    Container class for RSIs.  This serves as a class from which RateStructureItem instances are obtained
    via definition in the rs yaml. An RSI consists of (importantly) a descriptor, quantity, rate and total.
    The descriptor must be set in yaml and map to the bill xml @rsbinding for a given charge.
    The quantity may be a number or a python expression, usually the variable of a register in the rate_structure.
    In cases where these RateStructureItem attributes are absent in yaml, the rate_structure_item can
    calculate them.  A notable example is total, which is usually not set in the rs yaml except for
    fixed charges, like a customer charge. 
    RSIs track their values as instance variables that match the properties in yaml but prepended with an underscore.
    RSIs internally represent the properties from yaml as strings, but externally return the type from the eval(expr)
    operation.
    """

    # allow printing this object to evaluate the rate structure properties
    # __str__ seems to bury exceptions, so not necessary the best thing 
    # to have enabled during development.
    #TODO: better name
    deepprint = True

    # set by the ratestructure that contains the rate_structure_items
    _rate_structure = None

    def __init__(self, props, rate_structure):
        """
        Instantiate an RSI with a dictionary of RSI properties that come from the 'rates:' list in YAML
        file used to instantiate the parent RateStructure.
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
                # make sure everything is a string, with contents,  for the eval() function
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

    @property
    def descriptor(self):
        if hasattr(self, "_descriptor"):
            return self._descriptor
        else:
            return None

    def evaluate_rsi(self, rsi_value):
        """
        An RSI value is an str that has an expression that may be evaluated.
        An RSI expression can be as simpe as a number, or as complex as a Python
        statement that references values of other RSIs.
        Should the expression fail to evaluate, None is returned and the RSI is
        flagged as having an error.
        """
        assert type(rsi_value) is str

        try:

            # eval results in a recursive evaluation of all referenced expressions
            result = eval(rsi_value, self._rate_structure.__dict__)
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

        if hasattr(self, "_total"):
            return self.evaluate_rsi(self._total)

        # total isn't defined by RSI, so it must be computed
        else:

            # total must be computed from rate and/or quantity.

            # TODO: consider the meaning of the possible existing rate and quantity for the RSI
            # even though it has a total.  What if r and q are set and don't equal a total that has been set?!

            # TODO: it total exists, and either rate or quantity is missing, why not solve for
            # the missing term?

            # Look for a quantity, but it is ok if it does not exist - provided there is a rate
            q = self.quantity if hasattr(self, "_quantity") else None

            # Look for a rate and let the exception fly if it does not exist
            r = self.rate
                
            # A quantity and rate must be set to evaluate total.
            if q is not None:
                #print "%s: %s = %s * %s (%s)" % (self.descriptor, self._total, q, r, self.description)
                self._total = str(q * r)

            # No quantity, but there is a rate. 
            # A flat rate assumption can be made.
            elif q is None:
                self._total = str(1 * r)

            rule = self._roundrule if hasattr(self, "_roundrule") else None
            # we can set self._total if we want to compute only once
            #TODO: flag for compute once

            # perform decimal round rule.  Preserve native type. 
            return float(Decimal(str(self._total)).quantize(Decimal('.01'), rule))

    @property
    def description(self):

        if hasattr(self, "_description"):
            return self._description
        else:
            return None

    @property
    def quantity(self):

        if hasattr(self, "_quantity"):
            result = self.evaluate_rsi(self._quantity)
            return result

        raise NoPropertyError(self._descriptor, "%s.quantity does not exist" % self._descriptor)

    #@quantity.setter
    #def quantity(self, quantity):
    #    self._quantity = str(quantity)

    @property
    def quantityunits(self):

        if hasattr(self, "_quantityunits"):
            return self._quantityunits
        else:
            return None

    @property
    def rate(self):

        if hasattr(self, "_rate"):
            result = self.evaluate_rsi(self._rate)
            return result

        raise NoPropertyError(self._descriptor, "%s.rate does not exist" % self._descriptor)

    @property
    def rateunits(self):

        return self._rateunits if hasattr(self, "_rateunits") else None

    @property
    def roundrule(self):

        return self._roundrule if hasattr(self, "_roundrule") else None

    def __str__(self):

        s = 'Unevaluated RSI\n'
        s += 'descriptor: %s\n' % (self._descriptor if hasattr(self, '_descriptor') else '')
        s += 'description: %s\n' % (self._description if hasattr(self, '_description') else '')
        s += 'quantity: %s\n' % (self._quantity if hasattr(self, '_quantity') else '')
        s += 'quantityunits: %s\n' % (self._quantityunits if hasattr(self, '_quantityunits') else '')
        s += 'rate: %s\n' % (self._rate if hasattr(self, '_rate') else '')
        s += 'rateunits: %s\n' % (self._rateunits if hasattr(self, '_rateunits') else '')
        s += 'roundrule: %s\n' % (self._roundrule if hasattr(self, '_roundrule') else '')
        s += 'total: %s\n' % (self._total if hasattr(self, '_total') else '')
        s += '\n'
        if self.deepprint is True:
            s += 'Evaluated RSI\n'
            s += 'descriptor: %s\n' % (self.descriptor)
            s += 'description: %s\n' % (self.description)
            s += 'quantity: %s\n' % (self.quantity)
            s += 'quantityunits: %s\n' % (self.quantityunits)
            s += 'rate: %s\n' % (self.rate)
            s += 'rateunits: %s\n' % (self.rateunits)
            s += 'roundrule: %s\n' % (self.roundrule)
            s += 'total: %s\n' % (self.total)
            s += '\n'
        return s

class RateStructureItemNew():
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
                # make sure everything is a string, with contents,  for the eval() function
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

    @property
    def descriptor(self):
        if hasattr(self, "_descriptor"):
            return self._descriptor
        else:
            return None

    def evaluate_rsi(self, rsi_value):
        """
        An RSI value is an str that has an expression that may be evaluated.
        An RSI expression can be as simpe as a number, or as complex as a Python
        statement that references values of other RSIs.
        Should the expression fail to evaluate, None is returned and the RSI is
        flagged as having an error.
        """
        assert type(rsi_value) is str

        try:

            # eval results in a recursive evaluation of all referenced expressions
            result = eval(rsi_value, self._rate_structure.__dict__)
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

        if hasattr(self, "_total"):
            return self.evaluate_rsi(self._total)

        # total isn't defined by RSI, so it must be computed
        else:

            # total must be computed from rate and/or quantity.

            # TODO: consider the meaning of the possible existing rate and quantity for the RSI
            # even though it has a total.  What if r and q are set and don't equal a total that has been set?!

            # TODO: it total exists, and either rate or quantity is missing, why not solve for
            # the missing term?

            # Look for a quantity, but it is ok if it does not exist - provided there is a rate
            q = self.quantity if hasattr(self, "_quantity") else None

            # Look for a rate and let the exception fly if it does not exist
            r = self.rate
                
            # A quantity and rate must be set to evaluate total.
            if q is not None:
                #print "%s: %s = %s * %s (%s)" % (self.descriptor, self._total, q, r, self.description)
                self._total = str(q * r)

            # No quantity, but there is a rate. 
            # A flat rate assumption can be made.
            elif q is None:
                self._total = str(1 * r)

            rule = self._roundrule if hasattr(self, "_roundrule") else None
            # we can set self._total if we want to compute only once
            #TODO: flag for compute once

            # perform decimal round rule.  Preserve native type. 
            return float(Decimal(str(self._total)).quantize(Decimal('.01'), rule))

    @property
    def description(self):

        if hasattr(self, "_description"):
            return self._description
        else:
            return None

    @property
    def quantity(self):

        if hasattr(self, "_quantity"):
            result = self.evaluate_rsi(self._quantity)
            return result

        raise NoPropertyError(self._descriptor, "%s.quantity does not exist" % self._descriptor)

    #@quantity.setter
    #def quantity(self, quantity):
    #    self._quantity = str(quantity)

    @property
    def quantityunits(self):

        if hasattr(self, "_quantityunits"):
            return self._quantityunits
        else:
            return None

    @property
    def rate(self):

        if hasattr(self, "_rate"):
            result = self.evaluate_rsi(self._rate)
            return result

        raise NoPropertyError(self._descriptor, "%s.rate does not exist" % self._descriptor)

    @property
    def rateunits(self):

        return self._rateunits if hasattr(self, "_rateunits") else None

    @property
    def roundrule(self):

        return self._roundrule if hasattr(self, "_roundrule") else None

    def __str__(self):

        s = 'Unevaluated RSI\n'
        s += 'descriptor: %s\n' % (self._descriptor if hasattr(self, '_descriptor') else '')
        s += 'description: %s\n' % (self._description if hasattr(self, '_description') else '')
        s += 'quantity: %s\n' % (self._quantity if hasattr(self, '_quantity') else '')
        s += 'quantityunits: %s\n' % (self._quantityunits if hasattr(self, '_quantityunits') else '')
        s += 'rate: %s\n' % (self._rate if hasattr(self, '_rate') else '')
        s += 'rateunits: %s\n' % (self._rateunits if hasattr(self, '_rateunits') else '')
        s += 'roundrule: %s\n' % (self._roundrule if hasattr(self, '_roundrule') else '')
        s += 'total: %s\n' % (self._total if hasattr(self, '_total') else '')
        s += '\n'
        if self.deepprint is True:
            s += 'Evaluated RSI\n'
            s += 'descriptor: %s\n' % (self.descriptor)
            s += 'description: %s\n' % (self.description)
            s += 'quantity: %s\n' % (self.quantity)
            s += 'quantityunits: %s\n' % (self.quantityunits)
            s += 'rate: %s\n' % (self.rate)
            s += 'rateunits: %s\n' % (self.rateunits)
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



