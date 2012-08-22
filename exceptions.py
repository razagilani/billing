class Unauthenticated(Exception):
    pass


# TODO rename to NoSuchBillException
class NoSuchReeBillException(Exception):
    pass

class NoRateStructureError(Exception):
    pass
class NoUtilityNameError(Exception):
    pass
class IssuedBillError(Exception):
    '''Exception for trying to modify a bill that has been issued. Use this in
    all those situations.'''
    pass

class RSIError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, descriptor, msg):
        self.descriptor = descriptor
        self.msg = msg
    def __str__(self):
        return "%s %s" % (self.descriptor, self.msg)

# errors that occur during evaluation of rate structure "quantity" expressions

class RecursionError(RSIError):
    pass

class NoPropertyError(RSIError):
    pass

class NoSuchRSIError(RSIError):
    pass

class BadExpressionError(RSIError):
    pass
