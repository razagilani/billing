from itertools import islice
import logging
import os
import traceback
from brokerage.brokerage_model import Company
from brokerage.quote_parsers import DirectEnergyMatrixParser, USGEMatrixParser
from core.model import AltitudeSession, Session, Supplier

LOG_NAME = 'read_quotes'

# TODO: this class has no test coverage
class QuoteFileProcessor(object):
    """Checks for files containing matrix quotes in a particular directory,
    transfers quotes from them into a database, and deletes them.
    """
    # maps each supplier id to the class for parsing its quote file
    CLASSES_FOR_SUPPLIERS = {
        14: DirectEnergyMatrixParser,
        # 95: AEP
        199: USGEMatrixParser,
    }

    # number of quotes to read and insert at once. larger is faster as long
    # as it doesn't use up too much memory. (1000 is the maximum number of
    # rows allowed per insert statement in pymssql.)
    BATCH_SIZE = 1000

    def __init__(self):
        from core import config
        self.logger = logging.getLogger(LOG_NAME)
        self.quote_directory_path = config.get('brokerage', 'quote_directory')
        self.altitude_session = AltitudeSession()

    def _read_file(self, quote_file, supplier, altitude_supplier):
        """Read and insert 'BATCH_SIZE' quotes fom the given file.
        :param quote_file: quote file to read from
        :param supplier: core.model.Supplier instance
        :param altitude_supplier: brokerage.brokerage_model.Company instance
        corresponding to the Company table in the Altitude SQL Server database,
        representing a supplier. Not to be confused with the "supplier" table
        (core.model.Supplier) or core.altitude.AltitudeSupplier which is a
        mapping between these two. May be None if the supplier is unknown.
        """
        quote_parser = self.CLASSES_FOR_SUPPLIERS[supplier.id]()
        quote_parser.load_file(quote_file)
        quote_parser.validate()

        generator = quote_parser.extract_quotes()
        while True:
            quote_list = []
            for quote in islice(generator, self.BATCH_SIZE):
                if altitude_supplier is not None:
                    quote.supplier_id = altitude_supplier.company_id
                quote.validate()
                quote_list.append(quote)
            self.altitude_session.bulk_save_objects(quote_list)
            # TODO: probably not a good way to find out that the parser is done
            if quote_list == []:
                break
            yield quote_parser.get_count()

    def run(self):
        """Open, process, and delete quote files for all suppliers.
        """
        for supplier in Session().query(Supplier).filter(
                        Supplier.matrix_file_name != None).order_by(
            Supplier.name):
            # check if the file for this supplier exists and is writable
            path = os.path.join(self.quote_directory_path,
                                supplier.matrix_file_name)
            if not os.access(path, os.W_OK):
                self.logger.info('Skipped "%s": not found' % path)
                continue

            # match supplier in Altitude database by name--this means names
            # for the same supplier must always be the same (will be None if
            # not found)
            altitude_supplier = self.altitude_session.query(Company).filter_by(
                name=supplier.name).first()

            # load quotes from the file into the database, then delete the file
            try:
                with open(path, 'rb') as quote_file:
                    self.logger.info('Starting to read from "%s"' % path)
                    for count in self._read_file(quote_file, supplier,
                                                 altitude_supplier):
                        self.logger.debug('%s quotes so far' % count)
                    self.altitude_session.commit()
                os.remove(path)
            except Exception as e:
                self.logger.error('Error when processing "%s":\n%s' % (
                    path, traceback.format_exc()))
                self.altitude_session.rollback()
            else:
                # total should be 106560 from Direct Energy spreadsheet
                self.logger.info('Read %s quotes from "%s"' % (count, path))
        Session.remove()
        AltitudeSession.remove()