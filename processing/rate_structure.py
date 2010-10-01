import yaml
from decimal import *

class rate_structure(yaml.YAMLObject):
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


        for rsi in self.rates:
            # so that rate structure items may be referenced this objects namespace
            self.__dict__[rsi.descriptor] = rsi
            # so that RSIs have access to this objects namespace
            rsi.ratestructure = self

class register(yaml.YAMLObject):
    yaml_tag = u'!register'

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
        elif (name == 'total'):
            #print str(type(object.__getattribute__(self, 'total'))) + str(object.__getattribute__(self, 'total'))
            # if the total is a string, an expression, eval it
            if (type(object.__getattribute__(self, 'total')) == str):
                # assign eval results to attribute if re-evaluation doesn't have to be done. self.total = eval(...)
                return eval(object.__getattribute__(self, 'total'), object.__getattribute__(self, 'ratestructure').__dict__)
            if (type(object.__getattribute__(self, 'total')) == type(None)):
                print "Evaluating total"
                # total is not set, therefore, evaluate it.
                self.total = self.quantity * self.rate
            # otherwise just return the total since it does not have to be evaluated
            #return self.__dict__['total']
            return object.__getattribute__(self, 'total')
        else:
            return object.__getattribute__(self, name)
