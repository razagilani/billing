import yaml
from decimal import *

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

        # so that registers may be referenced from this obects namespace
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
    # like 'total' must be declared somewhere, if not they yaml.  So we declare them here.
    # And later ask if the value of the attribute is None to determine how processing occurs
    total = None


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
                # when calculating, charge items not later... No doubt this is going to vary across utilities

                # TODO: figure out how to do monetary rounding here
                try:
                    self.total = self.quantity * self.rate
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

    def __str__(self):

        s = ''
        s += 'descriptor: %s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += 'description: %s\t' % (self.description if hasattr(self, 'description') else '')
        s += 'quantity: %s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += 'quantityunits: %s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += 'rate: %s\t' % (self.rate if hasattr(self, 'rate') else '')
        s += 'rateunits: %s\t' % (self.rateunits if hasattr(self, 'rateunits') else '')
        s += 'total: %s\t' % (self.total if hasattr(self, 'total') else '')

        s += '\n'
        return s
        
