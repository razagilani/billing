"""Exceptions used with Billing.

The base exception class is :exc:`.BillingError`.
"""

class BillingError(Exception):
    """Generic error class."""

class DatabaseError(BillingError):
    """Raised when we have a database-related problem"""

