"""Read and parse and email with a matrix quote spreadsheet attachment from
stdin. Can be triggered by Postfix.
"""
import logging
import os
import traceback
from brokerage.brokerage_model import Company
from core import init_altitude_db, init_config, init_logging, init_model
from core.model import AltitudeSession, Session, Supplier
from brokerage.read_quotes import DirectEnergyMatrixParser

# TODO: can't get log file to appear where it's supposed to
LOG_NAME = 'read_quotes'

# where to look for quotes
QUOTE_DIRECTORY_PATH = '/tmp'

def get_files():
    logger = logging.getLogger(LOG_NAME)

    s = Session()
    altitude_session = AltitudeSession()

    for supplier in s.query(Supplier).filter(
                    Supplier.matrix_file_name != None).order_by(Supplier.id):
        file_name = supplier.matrix_file_name
        full_path = os.path.join(QUOTE_DIRECTORY_PATH, file_name)
        if not os.access(full_path, os.W_OK):
            logger.info('Skipped "%s"' % file_name)
            continue

        # match supplier in Altitude database by name--this means names for the
        # same supplier must always be the same
        altitude_supplier = altitude_session.query(Company).filter_by(
            name=supplier.name).one()

        count = 0
        try:
            with open(full_path, 'rb') as quote_file:
                quote_parser = DirectEnergyMatrixParser()
                logger.info('Starting to read from "%s"' % file_name)
                quote_parser.load_file(quote_file)
                quote_parser.validate()
                for quote in quote_parser.extract_quotes():
                    quote.supplier_id = altitude_supplier.company_id
                    altitude_session.add(quote)
                    count += 1
                    if count % 100 == 0:
                        altitude_session.flush()
                        logger.debug('%s quotes so far' % count)
                altitude_session.commit()
            os.remove(full_path)
        except Exception as e:
            logger.error('Error when processing "%s":\n%s' % (
                file_name, traceback.format_exc()))
            altitude_session.rollback()
        else:
            logger.info('Read %s quotes from "%s"' % (count, file_name))
    Session.remove()
    AltitudeSession.remove()

if __name__ == '__main__':
    init_config()
    init_logging()
    init_altitude_db()
    init_model()
    get_files()
