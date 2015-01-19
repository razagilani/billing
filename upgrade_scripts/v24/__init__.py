from upgrade_scripts import alembic_upgrade
import logging
from billing import config, init_model
from billing.core.model.model import Session

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 24')
    #init_model(schema_revision='5a6d7e4f8b80')
    s = Session()

    log.info('Upgrading schema to revision 3cf530e68eb')
    alembic_upgrade('3cf530e68eb')

    log.info('committing to Database')
    s.commit()

    log.info('Upgrade Complete')

