"""Miscellaneous helper functions/classes for Bill Entry.

This module's name comes from the recommended project structure at
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
If it gets big, it should become a multi-file module as shown there.
"""
from flask.ext.bcrypt import Bcrypt
from sqlalchemy.orm import make_transient
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
    the_id = utilbill.id
    s = Session.object_session(utilbill)
    utilbill.discriminator = BEUtilBill.POLYMORPHIC_IDENTITY
    sql = ("update %(table)s " "set discriminator = '%(discriminator)s' where id = %(id)d") % dict(
        table=UtilBill.__table__.name,
        discriminator=BEUtilBill.POLYMORPHIC_IDENTITY, id=utilbill.id)
    s.execute(sql)
    #s.flush()
    #s.expire_all()
    #s.refresh(utilbill)
    s.commit()
    Session.remove()
    utilbill = s.query(BEUtilBill).filter_by(id=the_id).one()
    # if this prints "beutilbill <class 'billentry.billentry_model.BEUtilBill'> True", it was successful:
    print utilbill.discriminator, utilbill.__class__, isinstance(utilbill, BEUtilBill)

    #make_transient(utilbill)
    return utilbill

_bcrypt = None

def get_bcrypt_object():
    global _bcrypt
    if _bcrypt is None:
        _bcrypt = Bcrypt()
    return _bcrypt