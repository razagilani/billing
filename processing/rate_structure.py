#!/usr/bin/python
import sys
import yaml
import jinja2
import os
from decimal import Decimal
import traceback

import pymongo

from billing import mongo
import yaml

class RateStructureDAO():

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


    def load_rs(self, account, sequence, rsbinding, branch):

        rate_structure = yaml.load(file(os.path.join(self.config["rspath"], rsbinding, account, sequence+".yaml")))

        # no mongo doc? make one to populate mongo.
        if self.load_rs_mongo(account, sequence, rsbinding, branch) is None:
            self.save_rs_mongo(account, sequence, rsbinding, branch, rate_structure)

        return rate_structure

    def load_rs_mongo(self, account, sequence, rsbinding, branch):

        mongo_rate_structure = self.collection.find_one({
            '_id': {
                    'account': account,
                    'sequence': sequence,
                    'branch': branch,
                    'rsbinding': rsbinding
            }
        })

        return mongo_rate_structure



    def save_rs_mongo(self, account, sequence, rsbinding, branch, rate_structure):

        rate_structure['_id'] = { 
            'account': account,
            'sequence': sequence,
            'branch': branch,
            'rsbinding': rsbinding
        }

        rate_structure = mongo.bson_convert(rate_structure)

        self.collection.save(rate_structure)

    def save_rs(self, account, sequence, rsbinding, rate_structure):

        yaml.safe_dump(rate_structure, open(os.path.join(self.config["rspath"], rsbinding, account, sequence+".yaml"), "w"), default_flow_style=False)
        self.save_rs_mongo(account, sequence, rsbinding, 0, rate_structure)



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
