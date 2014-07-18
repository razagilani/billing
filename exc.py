"""Exceptions used with Billing.

The base exception class is :exc:`.BillingError`.
"""


class BillingError(Exception):
    """Generic error class."""


class DatabaseError(BillingError):
    """Raised when we have a database-related problem"""


class InvalidParameter(BillingError):
    """Raised when function is called with invalid parameters"""
