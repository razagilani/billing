"""Exceptions used with Billing.

The base exception class is :exc:`.BillingError`.
"""


class BillingError(Exception):
    """Generic error class."""


class DatabaseError(BillingError):
    """Raised when we have a database-related problem"""


class InvalidParameter(BillingError):
    """Raised when function is called with invalid parameters"""


class Unauthenticated(BillingError):
    """"""


class MissingDataError(BillingError):
    """Data from an external source (e.g. Skyline OLAP or OLTP) were expected
    but not found."""


class NoSuchBillException(BillingError):
    pass


class NotUniqueException(BillingError):
    pass


class NoRateStructureError(BillingError):
    pass


class NoUtilityNameError(BillingError):
    pass


class RegisterError(BillingError):
    pass

class IssuedBillError(BillingError):
    """Exception for trying to modify a bill that has been issued.
    NOTE: keep this distinct from BillStateError, because it often means an
    attempt to save changes to an issued reebill document in mongo, not failure
    of a bill-processing operation due to a business rule."""


class BillStateError(BillingError):
    """A bill was in a state in which some operation is not allowed."""


# TODO maybe remove; BillStateError is specific enough
class NotAttachable(BillStateError):
    """Trying to issue a bill that is not issuable."""


class NotIssuable(BillStateError):
    """Trying to issue a bill that is not issuable."""


class RSIError(BillingError):
    """Error involving a Rate Structure Item."""


class NoRSIError(RSIError):
    """Trying to compute a charge that no corresponding Rate Structure Item."""


class FormulaError(RSIError):
    """Error in the "quantity"/"rate" formula of a Rate Structure Item."""


class FormulaSyntaxError(FormulaError):
    """Syntax error in the "quantity"/"rate" formula of a Rate Structure Item.
    Python SyntaxError should not be caught for obvious reasons."""


class NoSuchRSIError(RSIError):
    """Could not find the requested RSI"""


class MongoError(BillingError):
    """MongoDB write error: encapsulates the dictionary returned by PyMongo
    collection save/remove (when using "safe mode," which we should always be
    using)."""

    def __init__(self, err_dict):
        self.err_dict = err_dict

    def __str__(self):
        return str(self.err_dict)
