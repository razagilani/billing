class Unauthenticated(Exception):
    pass

class MissingDataError(Exception):
    '''Data from an external source (e.g. Skyline OLAP or OLTP) were expected
    but not found.'''
    pass

# TODO rename to NoSuchBillException
class NoSuchBillException(Exception):
    pass

class NotUniqueException(Exception):
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

class MongoError(Exception):
    '''MongoDB write error: encapsulates the dictionary returned by PyMongo
    collection save/remove (when using "safe mode," which we should always be
    using).'''
    def __init__(self, err_dict):
        self.err_dict = err_dict
    def __str__(self):
        return str(self.err_dict)
