"""Upgrade script for version 25.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import logging
from billentry.billentry_model import Role

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session


log = logging.getLogger(__name__)


def set_discriminator(s):
    s.execute('update utilbill set discriminator = "utilbill"')
    s.execute('update utilbill join utility_account '
              'on utilbill.utility_account_id = utility_account.id '
              'join brokerage_account '
              'on brokerage_account.utility_account_id = utility_account.id '
              'set utilbill.discriminator = "beutilbill"')

def create_admin_role(s):
    admin_role = Role('admin', 'admin role for accessing Admin UI')
    s.add(admin_role)

def upgrade():
    log.info('Beginning upgrade to version 25')

    log.info('Upgrading schema to revision 52a7069819cb')
    alembic_upgrade('52a7069819cb')

    init_model(schema_revision='52a7069819cb')
    s = Session()
    set_discriminator(s)
    create_admin_role(s)
    s.commit()
