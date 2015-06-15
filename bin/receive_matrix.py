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

# TODO: name to distinguish from QuoteParser
class QuoteReader(object):
    def __init__(self):
        from core import config
        self.logger = logging.getLogger(LOG_NAME)
        self.quote_directory_path = config.get('brokerage', 'quote_directory')
        self.altitude_session = AltitudeSession()

    def _read_file(self, quote_file, altitude_supplier):
        num = 0
        # TODO: choose correct class
        quote_parser = DirectEnergyMatrixParser()
        quote_parser.load_file(quote_file)
        quote_parser.validate()
        for quote in quote_parser.extract_quotes():
            quote.supplier_id = altitude_supplier.company_id
            self.altitude_session.add(quote)
            num += 1
            if num % 100 == 0:
                yield num

    def run(self):
        """Open, process, and delete quote files for all suppliers.
        """
        for supplier in Session().query(Supplier).filter(
                        Supplier.matrix_file_name != None).order_by(
            Supplier.id):
            # check if the file for this supplier exists and is writable
            path = os.path.join(self.quote_directory_path,
                                supplier.matrix_file_name)
            if not os.access(path, os.W_OK):
                self.logger.info('Skipped "%s"' % path)
                continue

            # match supplier in Altitude database by name--this means names
            # for the same supplier must always be the same
            altitude_supplier = self.altitude_session.query(Company).filter_by(
                name=supplier.name).one()

            # load quotes from the file into the database, then delete the file
            count = 0
            try:
                with open(path, 'rb') as quote_file:
                    self.logger.info('Starting to read from "%s"' % path)
                    for num in self._read_file(quote_file, altitude_supplier):
                        count += num
                        self.altitude_session.flush()
                        self.logger.debug('%s quotes so far' % count)
                    self.altitude_session.commit()
                os.remove(path)
            except Exception as e:
                self.logger.error('Error when processing "%s":\n%s' % (
                    path, traceback.format_exc()))
                self.altitude_session.rollback()
            else:
                self.logger.info('Read %s quotes from "%s"' % (count, path))
        Session.remove()
        AltitudeSession.remove()

if __name__ == '__main__':
    init_config()
    init_logging()
    init_altitude_db()
    init_model()

    QuoteReader().run()
