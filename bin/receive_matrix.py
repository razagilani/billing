"""Read and parse and email with a matrix quote spreadsheet attachment from
stdin. Can be triggered by Postfix.
"""
import logging
import os
import traceback
from core import init_altitude_db, init_config, init_logging, init_model
from core.model import AltitudeSession, Session
from brokerage.read_quotes import DirectEnergyMatrixParser

# TODO: can't get log file to appear where it's supposed to
LOG_NAME = 'read_quotes'

# where to look for quotes
QUOTE_DIRECTORY_PATH = '/tmp'

# maps file names supplier primary keys.
# only quote files with these names will be processed.
FILE_NAMES_SUPPLIERS = {
    'directenergy.xlsm': 13,
    'aep.xls': 95,
}

def get_files():
    logger = logging.getLogger(LOG_NAME)

    #s = AltitudeSession()
    s = Session()

    for file_name, supplier_id in FILE_NAMES_SUPPLIERS.iteritems():
        full_path = os.path.join(QUOTE_DIRECTORY_PATH, file_name)
        if not os.access(full_path, os.W_OK):
            logger.info('Skipped "%s"' % file_name)
            continue
        count = 0
        try:
            with open(full_path, 'rb') as quote_file:
                quote_parser = DirectEnergyMatrixParser()
                quote_parser.load_file(quote_file)
                quote_parser.validate()
                for quote in quote_parser.extract_quotes():
                    quote.supplier_id = supplier_id
                    s.add(quote)
                    s.flush()
                    count += 1
                s.commit()
            os.remove(full_path)
        except Exception as e:
            logger.error('Error when processing "%s":\n%s' % (
                file_name, traceback.format_exc()))
            s.rollback()
        else:
            logger.info('Read %s quotes from "%s"' % (count, file_name))

if __name__ == '__main__':
    init_config()
    init_logging()
    init_altitude_db()
    init_model()
    get_files()
