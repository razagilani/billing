import logging
from brokerage.brokerage_model import MatrixFormat
from upgrade_scripts import alembic_upgrade
from reebill.reebill_model import ReeBillCustomer, ReeBill
from sqlalchemy import desc
from core.model import Session, Base, Address
from core import init_model

log = logging.getLogger(__name__)

def update_reebill_customer_addresses():
    s = Session()
    customers = s.query(ReeBillCustomer).all()
    address = Address()
    for customer in customers:
        reebill = s.query(ReeBill).filter(ReeBill.reebill_customer==customer).order_by(desc(ReeBill.sequence)).first()
        if reebill is not None:
            customer.service_address = reebill.service_address
            customer.billing_address = reebill.billing_address
        else:
            customer.service_address = address
            customer.billing_address = address

def upgrade():
    alembic_upgrade('4f589e8d4cab')

    init_model(schema_revision='4f589e8d4cab')
    Base.metadata.reflect()
    s = Session()

    # create MatrixFormat objects, which now contain the
    # matrix_attachment_name column.
    # the Supplier.matrix_attachment_name attribute removed but the
    # supplier.matrix_attachement_name column still exists in the database. i
    # couldn't figure out the fancy SQLAlchemy way to add such a hidden
    # column to the query, so:
    cur = s.execute("select name, id, matrix_attachment_name from supplier "
                    "where matrix_email_recipient is not null")
    for name, supplier_id, matrix_attachment_name in cur.fetchall():
        s.add(MatrixFormat(name=name, supplier_id=supplier_id,
                           matrix_attachment_name=matrix_attachment_name))
        log.info('Created MatrixFormat for supplier %s "%s"' % (
            supplier_id, name))
    alembic_upgrade('5999376fe57d')
    #init_model(schema_revision='5999376fe57d')
    update_reebill_customer_addresses()
    s.commit()
    alembic_upgrade('2d5527ff438a')
    init_model(schema_revision='2d5527ff438a')
    s.commit()
