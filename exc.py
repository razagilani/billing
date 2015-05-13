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

class MissingFileError(BillingError):
    pass

class DuplicateFileError(BillingError):
    '''Attempt to upload or recognize a utility bill file that already exists.
    '''
    pass

class NoSuchBillException(BillingError):
    pass


class RegisterError(BillingError):
    pass

class IssuedBillError(BillingError):
    """Exception for trying to modify a bill that has been issued.
    NOTE: keep this distinct from BillStateError, because it often means an
    attempt to save changes to an issued reebill document in mongo, not failure
    of a bill-processing operation due to a business rule."""

class UnEditableBillError(BillingError):
    """Exception for trying to modify a bill that has been processed."""


class BillStateError(BillingError):
    """A bill was in a state in which some operation is not allowed."""


class NotIssuable(BillStateError):
    """Trying to issue a bill that is not issuable."""

class NotProcessable(BillStateError):
    """Trying to mark bill as processed that does not have all
    neccessary data"""

class RSIError(BillingError):
    """Error involving a Rate Structure Item."""

class FormulaError(RSIError):
    """Error in the "quantity"/"rate" formula of a Rate Structure Item."""


class FormulaSyntaxError(FormulaError):
    """Syntax error in the "quantity"/"rate" formula of a Rate Structure Item.
    Python SyntaxError should not be caught for obvious reasons."""


class ConfirmAdjustment(Exception):
    def __init__(self, correction_sequences, total_adjustment):
        super(ConfirmAdjustment, self).__init__()
        self.correction_sequences = correction_sequences
        self.total_adjustment = total_adjustment


class ConfirmMultipleAdjustments(ConfirmAdjustment):
    def __init__(self, accounts):
        self.accounts = accounts


class BillingTestError(Exception):
    """ Generic error class for Exceptions raised in testing utilities
    """


class TestClientRoutingError(BillingTestError):
    """ The TestClient was unable to route a request
    """

class ValidationError(BillingError):
    pass


