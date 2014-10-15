#sample_prog.py
#TODO: Move this sample program outside of the /billing package.

"""Sample program showing how to initialize configuration, logging, and database
for an application using the Billing data model (such as Acquisitor).
"""

"""Initialize the application before other imports."""
from billing import initialize
initialize()

"""Now begin your application imports"""

import logging
from billing.processing.state import Session, Customer

log = logging.getLogger(__name__)

log.info('Application running')

s = Session()
for c in s.query(Customer).all():
    log.info('Customer name %s account %s' % (c.name, c.account))

log.info('All done!')
