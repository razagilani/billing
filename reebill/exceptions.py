from core.exc import BillingError, BillStateError


class Unauthenticated(BillingError):
    """"""


class InvalidParameter(BillingError):
    """Raised when function is called with invalid parameters"""


class MissingDataError(BillingError):
    """Data from an external source (e.g. Skyline OLAP or OLTP) were expected
    but not found."""


class IssuedBillError(BillingError):
    """Exception for trying to modify a bill that has been issued.
    NOTE: keep this distinct from BillStateError, because it often means an
    attempt to save changes to an issued reebill document in mongo, not failure
    of a bill-processing operation due to a business rule."""


class NotIssuable(BillStateError):
    """Trying to issue a bill that is not issuable."""


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
