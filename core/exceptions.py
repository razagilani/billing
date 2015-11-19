"""Exceptions used with Billing.

The base exception class is :exc:`.BillingError`.
"""


class BillingError(Exception):
    """Generic error class."""


class DatabaseError(BillingError):
    """Raised when we have a database-related problem"""


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


class UnEditableBillError(BillingError):
    """Exception for trying to modify a bill that has been processed."""


class BillStateError(BillingError):
    """A bill was in a state in which some operation is not allowed."""


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


class ValidationError(BillingError):
    pass


class ExtractionError(BillingError):
    """Error related to extracting data from bill files.
    """
    pass

class MatchError(ExtractionError):
    """Failed to find exactly one match for a regular expression when
    extracting data from text.
    """
    pass

class ConversionError(ExtractionError):
    """Failed to convert an extracted string into the expected type.
    """
    pass

class NoRSIBindingError(ConversionError):
    """
    Failed to find an appropriate rsi binding for a given charge on a bill.
    This likely means that the 'charge' was not an actual charge, and should
    be ignored.
    """
    pass

class MergeError(BillingError):
    """Accounts cannot be merged when all utility_accounts have reebills
    """

class ApplicationError(ExtractionError):
    """Failed to apply an extracted value to a bill.
    """
    pass
