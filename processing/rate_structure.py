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

    yaml_tag = u'!rate_structure_item'

    # set by the ratestructure
    ratestructure = None

    # hack that allows python code fragments to recursively evaluate, however there is no good means to check for cycles
    def __getattribute__(self, name):

        # object.__geta... call supermethod to preventing unexpected recursion here
        if (name == 'quantity'):
            #print str(type(object.__getattribute__(self, 'quantity'))) + str(object.__getattribute__(self, 'quantity'))
            # if the quantity is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'quantity')) == str):
                # assign eval results to attribute if re-evaluation doesn't have to be done. self.quantity = eval(...)
                return eval(object.__getattribute__(self, 'quantity'), object.__getattribute__(self, 'ratestructure').__dict__)
            # otherwise just return the quantity since it does not have to be evaluated
            return object.__getattribute__(self, 'quantity')
        if (name == 'rate'):
            # if the rate is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'rate')) == str):
                return eval(object.__getattribute__(self, 'rate'), object.__getattribute__(self, 'ratestructure').__dict__)
            return object.__getattribute__(self, 'rate')

        elif (name == 'total'):
            #print str(type(object.__getattribute__(self, 'total'))) + str(object.__getattribute__(self, 'total'))
            # if the total is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'total')) == str):
                # assign eval results to attribute if re-evaluation doesn't have to be done. self.total = eval(...)
                return eval(object.__getattribute__(self, 'total'), object.__getattribute__(self, 'ratestructure').__dict__)
            if (type(object.__getattribute__(self, 'total')) == type(None)):
                # total is not set, therefore, evaluate it.
                # Using python Decimal money math here since it appears utilities round up
                # when calculating, not later... No doubt this is going to vary across utilities

                # TODO: figure out how to do monetary rounding here
                self.total = self.quantity * self.rate
                return object.__getattribute__(self.total)

            # otherwise just return the total since it does not have to be evaluated
            # TODO figure out how to do moentary rounding here
            return object.__getattribute__(self, 'total')
        else:
            return object.__getattribute__(self, name)

    def __str__(self):

        s = ''
        s += '%s\t' % (self.descriptor if hasattr(self, 'descriptor') else '')
        s += '%s\t' % (self.description if hasattr(self, 'description') else '')
        s += '%s\t' % (self.quantity if hasattr(self, 'quantity') else '')
        s += '%s\t' % (self.quantityunits if hasattr(self, 'quantityunits') else '')
        s += '%s\t' % (self.rate if hasattr(self, 'rate') else '')
        s += '%s\t' % (self.rateunits if hasattr(self, 'rateunits') else '')
        s += '%s\t' % (self.total if hasattr(self, 'total') else '')

        s += '\n'
        return s
        
