#!/usr/bin/python

import yaml
import jinja2
import os
from decimal import Decimal
import traceback

class RateStructure():
    """ 
    A RateStructure consist of Registers and RateStructureItems.
    The rate structure is the model for how utilities calculate their utility bill.  This model does not
    necessarily dictate the re bill, because the re bill can have charges that are not part of this model.
    This is also why the rate structure model does not comprehend charge grouping, subtotals or totals.
    """
    def __init__(self, rs_yaml):
        """
        Construct with a loaded yaml file that contains the necessary fields for the ratestructure
        including registers and rate structure items.
        """

        self.__bind_yaml(rs_yaml)
        self.__bind_registers()
        self.__bind_rsi()

    def __bind_registers(self):
        # so that registers may be referenced from this objects namespace
        for reg in self.registers:
            if reg.descriptor is None:
                print "Register descriptor required.\n%s" % reg
                continue
            self.__dict__[reg.descriptor] = reg

    def __bind_rsi(self):
        # RSI fields like quantity and rate refer to values in other RSIs.
        # so a common namespace must exist for the eval() strategy found in RSIs.
        # Therefore, the RSIs are added to self by RSI Descriptor.
        # RSIs refer to other RSIs by Descriptor.
        for rsi in self.rates:
            if rsi.descriptor is None:
                print "RSI descriptor required.\n%s" % rsi
                continue
            self.__dict__[rsi.descriptor] = rsi
            # so that RSIs have access to this object's namespace and can
            # pass the ratestructure into eval as the global namespace
            rsi.ratestructure = self

    def __bind_yaml(self, rs_yaml):
        #TODO: graceful failure on bad yaml
        self.name = rs_yaml["name"]
        self.service = rs_yaml["service"]
        self.registers = [Register(reg_rs_yaml) for reg_rs_yaml in rs_yaml["registers"]]
        self.rates = [RateStructureItem(rsi_rs_yaml) for rsi_rs_yaml in rs_yaml["rates"]]

    def register_needs(self):
        """ Return a list of registers that must be populated with energy."""
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
    """ Container class for RSIs.  This serves as a class from which RateStructureItem instances are obtained """
    """ via definition in the rs yaml. An RSI consists of (importantly) a descriptor, quantity, rate and total.  """
    """ The descriptor must be set in yaml and map to the bill xml @rsbinding for a given charge."""
    """ The quantity may be a number or a python expression, usually the variable of a register in the rate_structure. """
    """ In cases where these RateStructureItem attributes are absent in yaml, the rate_structure_item can """
    """ calculate them.  A notable example is total, which is usually not set in the rs yaml except for """
    """ fixed charges, like a customer charge. """

    # allow printing this object to evaluate the rate structure properties
    # __str__ seems to bury exceptions, so not necessary the best thing 
    # to have enabled during development.
    deepprint = False

    # set by the ratestructure that contains the rate_structure_items
    ratestructure = None

    def __init__(self, props):
        """
        Instantiate an RSI with a dictionary of RSI properties that come from the 'rates:' list in YAML
        file used to instantiate the parent RateStructure.
        There are two allowed types for the values of an RSI property: String and Decimal.
        """

        for key in props:

            # all keys passed are prepended with an _
            # and directly set in this instance
            # because we cover these RSI instance attributes 
            # with an @property decorator to encapsulate
            # functionality required to dynamically 
            # evaluate those attributes

            # if a value exists in the rate
            value = props[key]
            if (value is not None):
                # use that value but change it to a Decimal if it is a float or int
                value = value if type(value) == str else Decimal(str(value))
                setattr(self, "_"+key, value)
                print "%s - %s:%s" % (key, props[key], str(type(value)))
            else:
                print "Warning: %s %s is an empty property" % (props["descriptor"], key)

    @property
    def descriptor(self):
        if hasattr(self, "_descriptor"):
            return self._descriptor
        else:
            return None

    def evaluate_rsi(self, rsi_value):
        """
        An RSI value may be one of a String as in the case of an expression,
        a Decimal as in the case of 
        """

        assert type(rsi_value) in [str, Decimal, type(None)]

        if type(rsi_value) is Decimal:
            return rsi_value

        elif type(rsi_value) is str:
            result = None
            try:
                result = eval(rsi_value, self.ratestructure.__dict__)
            except RuntimeError as re:
                print "Runtime Error"
                print str(re)
                print('Exception: %s' % re)
            except TypeError as te:
                print "Type Error"
                print str(te)
                print('Exception: %s' % te)
            return Decimal(str(result))
        elif type(rsi_value) is type(None):
            print "%s: Empty value" % self._descriptor
            return None
            


    @property
    def total(self):
        """
        """

        if hasattr(self, "_total") and self._total is not None:
            # it is either a string or a decimal
            return self.evaluate_rsi(self._total)

        # total wasn't defined in RS yaml, so it must be computed
        else:

            # total must be computed from rate and/or quantity.

            # TODO: consider the meaning of the possible existing rate and quantity for the RSI
            # even though it has a total.  What if r and q are set and don't equal total?!

            # TODO: it total exists, and either rate or quantity is missing, why not solve for
            # the missing term?

            # Access the public interface for quantity and rate
            # so that quantity and rate evaluate themselves
            q = self.quantity
            r = self.rate
                
            # A quantity and rate must be set to evaluate total.
            if q is not None and r is not None:
                print "Descriptor %s" % self.descriptor
                print "Q is %s " % type(q)
                print "R is %s " % type(r)
                self._total = q * r
                print "%s: %s = %s * %s (%s)" % (self.descriptor, self._total, q, r, self.description)
            # No quantity, but there is a rate. 
            # A flat rate assumption can be made.
            elif q is None and r is not None:
                self._total = Decimal("1") * r
            # No rate
            # No good assumptions can be made.
            else:
                raise Exception("Total cannot be determined - no rate")

            rule = self._roundrule if hasattr(self, "_roundrule") else None
            # we can set self._total if we want to compute only once
            #TODO: flag for compute once
            return Decimal(str(self._total)).quantize(Decimal('.01'), rule)


    @property
    def description(self):
        if hasattr(self, "_description"):
            return self._description
        else:
            return None

    @property
    def quantity(self):

        if hasattr(self, "_quantity"):
            assert(type(self._quantity) in [str, Decimal, type(None) ])
            if type(self._quantity) is str:
                # quantity is an expression and so must be 
                # evaluated in the context of the ratestructure
                quantity = None
                try:
                    quantity = eval(self._quantity, self.ratestructure.__dict__)
                    print "quantity evaluated to type %s" % type(quantity)
                except RuntimeError as re:
                    print "Runtime Error"
                    print str(re)
                    print('Exception: %s' % re)
                # quantity must be returned as a Decimal
                return Decimal(str(quantity))
            elif type(self._quantity) is Decimal:
                # quantity explicity set in yaml, so just return in
                return self._quantity
            else:
                # TODO: figure design out for quantities that are externally set
                print "Quantity does not have a value"
        else:
            print "%s: Quantity does not exist" % self._descriptor

        # quantity property does not exist
        return None

    @quantity.setter
    def quantity(self, quantity):
        self._quantity = Decimal(str(quantity))

    @property
    def quantityunits(self):
        if hasattr(self, "_quantityunits"):
            return self.quantityunits
        else:
            return None

    @property
    def rate(self):

        if hasattr(self, "_rate"):
            assert(type(self._rate) in [str, Decimal, type(None)])
            if type(self._rate) is str:
                # rate is an expression, and so must be 
                # evaluated in the context of the ratestructure
                rate = None
                try:
                    rate = eval(self._rate, self.ratestructure.__dict__)
                except RuntimeError as re:
                    print "Runtime Error"
                    print str(re)
                    print('Exception: %s' % re)
                return rate
            elif type(self._rate) is Decimal:
                # rate was explicity set in yaml, so just return it
                return self._rate
            else:
                # TODO: figure design out for rates that are externally set
                print "Rate does not have a value"
        else:
            print "%s: Rate does not exist" % self._descriptor

        # rate property does not exist
        return None

    @property
    def rateunits(self):
        if hasattr(self, "_rateunits"):
            return self.rateunits
        else:
            return None

    #@total.setter
    #def total(self, total):
        #print "Property set " + str(total)
        #self._total = total


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

class rate_structure_item(yaml.YAMLObject):
    """ Container class for RSIs.  This serves as a class from which rate_structure_item instances are obtained """
    """ via definition in the rs yaml. An RSI consists of (importantly) a descriptor, quantity, rate and total.  """
    """ The descriptor must be set in yaml and map to the bill xml @rsbinding for a given charge."""
    """ The quantity may be a number or a python expression, usually the variable of a register in the rate_structure. """
    """ The rate may be absent or a number. """
    """ The total may be absent or a number. """
    """ In cases where these rate_structure_items attributes are absent in yaml, the rate_structure_item can """
    """ calculate them.  A notable example is total, which is usually not set in the rs yaml except for """
    """ fixed charges, like a customer charge. """


    yaml_tag = u'!rate_structure_item'

    # set by the ratestructure that contains the rate_structure_items
    ratestructure = None

    # Declare the attributes that make an RSI.  
    # This is done because it is not mandatory to declare such attributes in the rs yaml
    # If the attributes are not declared in the rs yaml, errors will occur if those
    # attributes are accessed in an instance of a rate_structure_item and do not exist.
    # And because of the __getattribute__ hack below, attributes that are dynamically computed
    # like 'total' must be declared somewhere, if not the yaml.  So we declare them here.
    # And later ask if the value of the attribute is None to determine how processing occurs
    total = None
    quantity = None
    rate = None

    """
    # hack that allows python code fragments to recursively evaluate, however there is no good means to check for cycles
    def __getattribute__(self, name):

        # if this RSI does not yet have its ratestructure set and the ratestructure __dict__ is not full of the 
        # register values that we need to evaluate RSIs, do nothing special
        if (object.__getattribute__(self, 'ratestructure') is None):
            return object.__getattribute__(self, name)
           
        # So now do something special since a ratestructure is available to this RSI
        # Basically, every time one of the RSI properties, quantity, rate or total is
        # accessed, eval it if it is a string using the ratestructure __dict__ as
        # its namespace

        # object.__getattribute__ is a call to a supermethod preventing recursion
        # what happens here is that for a rate_structure_item, quantity and rate,
        # for example, may need to be evaluated when the attribute total is accessed

        # handle requests for a rate_structure_item quantity.  This is usually a string that refers
        # to a register in the rate_structure's __dict__ or more interestingly, a subtotal of all
        # specified rate_structure_item descriptors in the event of a subtotal.
        if (name == 'quantity'):
            # consider testing for presence of attr, catching attribute error, printing msg and throwing the AE

            # if the quantity is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'quantity')) == str):

                # evaluate the string and return the result as the value of the quantity attribute
                return eval(object.__getattribute__(self, 'quantity'), object.__getattribute__(self, 'ratestructure').__dict__)
            # otherwise just play dumb and return the quantity since it does not or no longer has to be evaluated
            # playing dumb is smart for functions like hasattr() or other consumers of __getattribute__
            return object.__getattribute__(self, 'quantity')

        # handle requests for a rate_structure_item rate.  This is usually a number, but could be something
        # very complex like a declining block rate tax
        if (name == 'rate'):
            # consider testing for presence of attr, catching attribute error, printing msg and throwing the AE

            # if the rate is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'rate')) == str):

                # evaluate the string and return the result as the value of the rate attribute
                return eval(object.__getattribute__(self, 'rate'), object.__getattribute__(self, 'ratestructure').__dict__)
            # otherwise, just play dumb and return the rate - important for functions that depend on __getattribute__
            return object.__getattribute__(self, 'rate')

        elif (name == 'total'):
            if (type(object.__getattribute__(self, 'total')) == type(None)):

                # total is not set, therefore, evaluate it because we have enough information to do so.
                # TODO: check to make sure quantity and rate are set
                # Using python Decimal money math here since it appears utilities round up
                # when calculating charge items not later... No doubt this is going to vary across utilities

                # TODO: figure out how to do monetary rounding here
                try:
                    from decimal import Decimal
                    q = self.quantity
                    r = self.rate
                    rule = ""
                    try:
                        rule = self.roundrule if object.__getattribute__(self, 'roundrule') else None
                    except Exception, err:
                        print('Rounding rule: %s\n' % str(err))

                    t = self.quantity * self.rate 

                    if (rule):
                        t = float(Decimal(str(t)).quantize(Decimal('.01'), rule))

                    self.total = t

                except Exception, err:
                    print('ERROR: %s\n' % str(err))
                    raise AttributeError 

                return object.__getattribute__(self, 'total')

            # if the total is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'total')) == str):
                # assign eval results to attribute if re-evaluation doesn't have to be done. self.total = eval(...)
                return eval(object.__getattribute__(self, 'total'), object.__getattribute__(self, 'ratestructure').__dict__)

            # otherwise just return the total since it does not have to be evaluated
            # TODO figure out how to do moentary rounding here
            return object.__getattribute__(self, 'total')

        # we don't care about attributes that have nothing to do with the rate_structure_item yaml declared attrs
        else:
            return object.__getattribute__(self, name)

    """

    def __str__(self):

        s = ''
        s += 'descriptor: %s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += 'description: %s\t' % (self.description if hasattr(self, 'description') else '')
        s += 'quantity: %s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += 'quantityunits: %s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += 'rate: %s\t' % (self.rate if hasattr(self, 'rate') else '')
        s += 'rateunits: %s\t' % (self.rateunits if hasattr(self, 'rateunits') else '')
        s += 'roundrule: %s\t' % (self.roundrule if hasattr(self, 'roundrule') else '')
        s += 'total: %s\t' % (self.total if hasattr(self, 'total') else '')

        s += '\n'
        return s
        
class rate_structure(yaml.YAMLObject):
    """ The rate structure is the model for how utilities calculate their utility bill.  This model does not
    necessarily dictate the re bill, because the re bill can have charges that are not part of this model.
    This is also why the rate structure model does not comprehend charge grouping, subtotals or totals.
    """
    yaml_tag = u'!rate_structure'

    def register_needs(self):
        """ Return a list of registers that must be populated with energy."""
        needs = []
        for register in self.registers:
            if (register.quantity == None):
                needs.append(register)
        return needs

    def configure(self):
        """ After this rate_structure is loaded, add rsi descriptors to it. """

        # so that registers may be referenced from this objects namespace
        for reg in self.registers:
            self.__dict__[reg.descriptor] = reg

        # so that rate structure items may be referenced from this objects namespace
        for rsi in self.rates:
            self.__dict__[rsi.descriptor] = rsi
            # so that RSIs have access to this objects namespace
            rsi.ratestructure = self

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

class register(yaml.YAMLObject):
    yaml_tag = u'!register'

    def __str__(self):

        s = '' 
        s += '%s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += '%s\t' % (self.description if hasattr(self, 'description') else '')
        s += '%s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += '%s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += '\n'
        return s
