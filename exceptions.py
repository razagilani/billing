class Unauthenticated(Exception):
    pass

class MissingDataError(Exception):
    '''Data from an external source (e.g. Skyline OLAP or OLTP) were expected
    but not found.'''
    pass

# TODO rename to NoSuchBillException
class NoSuchBillException(Exception):
    pass

class NoRateStructureError(Exception):
    pass

class NoUtilityNameError(Exception):
    pass

class IssuedBillError(Exception):
    '''Exception for trying to modify a bill that has been issued.'''
    pass

class NotIssuable(Exception):
    '''Trying to issue a bill that is not issuable.'''

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
