"""Miscellaneous helper functions/classes for Bill Entry.

This module's name comes from the recommended project structure at
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
If it gets big, it should become a multi-file module as shown there.
"""
from flask.ext.bcrypt import Bcrypt

from billentry.billentry_model import BEUtilBill
from core.model import UtilBill, Session


def replace_utilbill_with_beutilbill(utilbill):
    """Return a BEUtilBill object identical to 'utilbill' except for its
    class, and delete 'utilbill' from the session. 'utilbill.id' is set to
    None because 'utilbill' no longer corresponds to a row in the database.
    Do not use 'utilbill' after passing it to this function.
    """
    assert type(utilbill) is UtilBill
    assert utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY
    s = Session.object_session(utilbill)
    # flushing changes too early causes conflict before utilbill is deleted
    with s.no_autoflush:
        beutilbill = BEUtilBill.create_from_utilbill(utilbill)
    s.add(beutilbill)
    s.delete(utilbill)
    utilbill.id = None
    return beutilbill

_bcrypt = None

def get_bcrypt_object():
    global _bcrypt
    if _bcrypt is None:
        _bcrypt = Bcrypt()
    return _bcrypt

def account_has_bills_for_data_entry(utility_account):
    return any(
        u.discriminator == BEUtilBill.POLYMORPHIC_IDENTITY and not
        u.is_entered()
        for u in utility_account.utilbills)
