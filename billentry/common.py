"""Miscellaneous helper functions/classes for Bill Entry.

This module's name comes from the recommended project structure at
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
If it gets big, it should become a multi-file module as shown there.
"""
from flask.ext.bcrypt import Bcrypt
from sqlalchemy.orm import make_transient
from billentry.billentry_model import BEUtilBill
from core.model import Session
from core.model.utilbill import UtilBill


def replace_utilbill_with_beutilbill(utilbill):
    """Return a BEUtilBill object identical to 'utilbill' except for its
    class, and expunge 'utilbill' from the session. The new BEUtilBill has
    the same id as 'utilbill' and corresponds to the same database row,
    but is a distinct object. The same applies to all child objects of the
    BEUtilBill.

    Do not use 'utilbill' or any of its child objects after passing it to
    this function, because they are no longer in the session.
    """
    assert type(utilbill) is UtilBill
    assert utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY
    s = Session.object_session(utilbill)
    utilbill.discriminator = BEUtilBill.POLYMORPHIC_IDENTITY
    # the change to utilbill.discriminator MUST be flushed here or it will be
    # discarded when 'utilbill' is expunged.
    s.flush()
    # remove 'utilbill' from the session. this is propagated to other objects
    # according to the SQLAlchemy cascade setting of the relationships
    # defined in UtilBill (if cascade='expunge' or cascade='all', as in the
    # case of 'billing_address' and 'service_address')
    s.expunge(utilbill)
    beutilbill = s.query(BEUtilBill).filter_by(id=utilbill.id).one()
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
