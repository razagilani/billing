import csv
from os.path import dirname, realpath, join
from billing.core.altitude import AltitudeUtility

def import_altitude_utilities(session):
    filepath = join(dirname(realpath(__file__)), 'utilities_suppliers.csv')
    with open(filepath) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if type == '1':
                # We're dealing with a Utility
                session.add(
                    AltitudeUtility()
                )
            return
# Map Billing to Portal
# 1:
#     1
#     7
# 2:
#     0
#     158
#     4
#     6
# 3:
#     13
# 4:
#     8
# 5:
#     3


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