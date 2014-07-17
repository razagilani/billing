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

class RegisterError(Exception):
    pass

# NOTE keep this distinct from BillStateError, because it often means an
# attempt to save changes to an issued reebill document in mongo, not failure
# of a bill-processing operation due to a business rule 
class IssuedBillError(Exception):
    '''Exception for trying to modify a bill that has been issued.'''
    pass

class BillStateError(Exception):
    '''A bill was in a state in which some operation is not allowed.'''
    pass

# TODO maybe remove; BillStateError is specific enough
class NotAttachable(BillStateError):
    '''Trying to issue a bill that is not issuable.'''
class NotIssuable(BillStateError):
    '''Trying to issue a bill that is not issuable.'''

class RSIError(Exception):
    '''Error involving a Rate Structure Item.
    '''
    pass

class NoRSIError(RSIError):
    '''Trying to compute a charge that no corresponding Rate Structure Item.
    '''
    pass

class FormulaError(RSIError):
    '''Error in the "quantity"/"rate" formula of a Rate Structure Item.
    '''
    pass

class FormulaSyntaxError(FormulaError):
    '''Syntax error in the "quantity"/"rate" formula of a Rate Structure Item.
    Python SyntaxError should not be caught for obvious reasons.
    '''
    pass

class NoSuchRSIError(RSIError):
    pass

class MongoError(Exception):
    '''MongoDB write error: encapsulates the dictionary returned by PyMongo
    collection save/remove (when using "safe mode," which we should always be
    using).'''
    def __init__(self, err_dict):
        self.err_dict = err_dict
    def __str__(self):
        return str(self.err_dict)

class RenderError(Exception):
    pass
