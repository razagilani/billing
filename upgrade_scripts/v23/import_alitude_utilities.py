import csv
import logging
from os.path import dirname, realpath, join
from billing.core.altitude import AltitudeUtility
from billing.core.model import Utility, Address

log = logging.getLogger(__name__)

def get_or_create_billing_utility_from_portal_id(session, portal_id,
                                                 utility_name):
    if portal_id == 1 or portal_id == 7:
        # Pepco
        return session.query(Utility).filter_by(id=1).one()
    elif portal_id == 0 or portal_id == 158 or portal_id == 4 or portal_id == 6:
        # Washington Gas
        return session.query(Utility).filter_by(id=2).one()
    elif portal_id == 13:
        # Piedmont
        return session.query(Utility).filter_by(id=3).one()
    elif portal_id == 8:
        # PECO
        return session.query(Utility).filter_by(id=4).one()
    elif portal_id == 3:
        # BGE
        return session.query(Utility).filter_by(id=5).one()
    else:
        u = Utility(utility_name, Address())
        session.add(u)
        return u


def import_csv_record(session, record):
    u = get_or_create_billing_utility_from_portal_id(
        session, int(record['id']), record['name']
    )
    au = AltitudeUtility(u, record['guid'])
    session.add(au)
    log.info("Linking Altitude Utility %s to Billing Utility %s",
             record['name'], u.name)


def import_altitude_utilities(session):
    filepath = join(dirname(realpath(__file__)), 'utilities_suppliers.csv')
    with open(filepath) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['type'] == '1':
                # We're dealing with a Utility
                import_csv_record(session, row)

if __name__ == '__main__':
    # for testing in development environment
    from billing import init_config, init_model, init_logging

    init_config()
    init_model()
    init_logging()
    from billing.core.model import Session

    session = Session()
    import_altitude_utilities(session)
    session.commit()