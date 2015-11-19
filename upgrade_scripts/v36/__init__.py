from upgrade_scripts import alembic_upgrade
from reebill.reebill_model import ReeBillCustomer
from core.model import Session
from core import init_model


def update_reebill_customer_addresses():
    s = Session()
    customers = s.query(ReeBillCustomer).all()
    for customer in customers:
        customer.service_address = customer.utility_account.fb_service_address
        customer.billing_address = customer.utility_account.fb_billing_address
    s.commit()

def upgrade():
    alembic_upgrade('5999376fe57d')
    init_model(schema_revision='5999376fe57d')
    update_reebill_customer_addresses()
    alembic_upgrade('2d5527ff438a')