from cStringIO import StringIO
import email
from itertools import islice
import logging
import re

from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from brokerage.brokerage_model import Company
from brokerage import quote_parsers
from core.model import AltitudeSession, Session, Supplier
from exc import BillingError
from util.email_util import get_attachments

LOG_NAME = 'read_quotes'

class QuoteProcessingError(BillingError):
    pass

class EmailError(QuoteProcessingError):
    """Email was invalid.
    """

class UnknownSupplierError(QuoteProcessingError):
    """Could not match the an email to a supplier, or more than one supplier
    matched it.
    """


class QuoteDAO(object):
    """Handles database access for QuoteEmailProcessor. Not sure if it's a
    good design to wrap the SQLAlchemy session object like this.
    """
    def __init__(self):
        self.altitude_session = AltitudeSession()

    def get_supplier_objects_for_message(self, from_addr, to_addr, subject):
        """Determine which supplier an email is from using the sender and
        recipient email addresses.

        Raise UnknownSupplierError if there was not exactly one supplier
        corresponding to the email in the main database and another with the
        same name in the Altitude database.

        :param from_addr: regular expression string for email sender address
        :param to_addr: regular expression string for email recipient address
        :param subject: regular expression string for email subject
        :return: core.model.Supplier representing the supplier table int the
        main database, brokerage.brokerage_model.Company representing the
        same supplier in the Altitude database.
        """
        q = Session().query(Supplier).filter(
            or_(Supplier.matrix_email_sender == None,
                Supplier.matrix_email_sender.like(from_addr)),
            or_(Supplier.matrix_email_recipient == None,
                Supplier.matrix_email_recipient.like(to_addr)),
            or_(Supplier.matrix_email_subject == None,
                Supplier.matrix_email_subject.like(subject)))
        try:
            supplier = q.one()
        except (NoResultFound, MultipleResultsFound):
            raise UnknownSupplierError

        # match supplier in Altitude database by name--this means names
        # for the same supplier must always be the same
        q = self.altitude_session.query(
            Company).filter_by(name=supplier.name)
        try:
            altitude_supplier = q.one()
        except (NoResultFound, MultipleResultsFound):
            raise UnknownSupplierError

        return supplier, altitude_supplier

    def insert_quotes(self, quote_list):
        """
        Insert Quotes into the Altitude database, using the SQLAlchemy "bulk
        insert" feature for performance.
        :param quote_list: iterable of Quote objects
        """
        self.altitude_session.bulk_save_objects(quote_list)

    def begin_nested(self):
        """Start nested transaction in Altitude database for one quote file.
        """
        self.altitude_session.begin_nested()

    def rollback(self):
        """Roll back Altitude database transaction to the last savepoint if
        an error happened while inserting quotes.
        """
        self.altitude_session.rollback()

    def commit(self):
        """Commit Altitude database transaction to permanently store inserted
        quotes.
        """
        self.altitude_session.commit()


CLASSES_FOR_SUPPLIERS = {
    14: quote_parsers.DirectEnergyMatrixParser,
    95: quote_parsers.AEPMatrixParser,
    199: quote_parsers.USGEMatrixParser,
}

class QuoteEmailProcessor(object):
    """Receives emails from suppliers containing matrix quote files as
    attachments, and extracts the quotes from the attachments.
    """
    # number of quotes to read and insert at once. larger is faster as long
    # as it doesn't use up too much memory. (1000 is the maximum number of
    # rows allowed per insert statement in pymssql.)
    BATCH_SIZE = 1000

    def __init__(self, classes_for_suppliers, quote_dao):
        """
        :param classes_for_suppliers: dictionary mapping the primary keys of
        each Supplier (Supplier.id) to the QuoteParser subclass that handles
        its file format.
        :param quote_dao: QuoteDAO object for handling database access.
        """
        self.logger = logging.getLogger(LOG_NAME)
        self._clases_for_suppliers = classes_for_suppliers
        self._quote_dao = quote_dao

    def _process_quote_file(self, supplier, altitude_supplier, file_content):
        """Process quotes from a single quote file for the given supplier.
        :param supplier: core.model.Supplier instance
        :param altitude_supplier: brokerage.brokerage_model.Company instance
        corresponding to the Company table in the Altitude SQL Server database,
        representing a supplier. Not to be confused with the "supplier" table
        (core.model.Supplier) or core.altitude.AltitudeSupplier which is a
        mapping between these two. May be None if the supplier is unknown.
        :param file_content: content of a quote file as a string. (A file
        object would be better, but the Python 'email' module processes a
        whole file at a time so it all has to be in memory anyway.)
        """
        # copy string into a StringIO :(
        quote_file = StringIO(file_content)

        # pick a QuoteParser class for the given supplier, and load the file
        # into it, and validate the file
        quote_parser = self._clases_for_suppliers[supplier.id]()
        quote_parser.load_file(quote_file)
        quote_parser.validate()

        # read and insert quotes in groups of 'BATCH_SIZE'
        generator = quote_parser.extract_quotes()
        while True:
            quote_list = []
            for quote in islice(generator, self.BATCH_SIZE):
                if altitude_supplier is not None:
                    quote.supplier_id = altitude_supplier.company_id
                quote.validate()
                quote_list.append(quote)
            self._quote_dao.insert_quotes(quote_list)
            count = quote_parser.get_count()
            # TODO: probably not a good way to find out that the parser is done
            if quote_list == []:
                return count
            self.logger.debug('%s quotes so far' % count)

    def process_email(self, email_file):
        """Read an email from the given file, which should be an email from a
        supplier containing one or more matrix quote files as attachments.
        Determine which supplier the email is from, and process each
        attachment using a QuoteParser to extract quotes from the file and
        store them in the Altitude database.

        If there are no attachments, nothing happens.

        Quotes inserted with a savepoint after each file is completed, so an
        error in a later file won't affect earlier ones.

        Raise EmailError if something went wrong with the email.
        Raise UnknownSupplierError if there was not exactly one supplier
        corresponding to the email in the main database and another with the
        same name in the Altitude database.
        Raise ValidationError if there was a problem with a quote file
        itself or the quotes in it.

        :param email_file: text file with the full content of an email
        """
        self.logger.info('Staring to read email')
        message = email.message_from_file(email_file)
        from_addr, to_addr = message['From'], message['To']
        subject = message['Subject']
        if None in (from_addr, to_addr, subject):
            raise EmailError('Invalid email format')

        supplier, altitude_supplier = \
            self._quote_dao.get_supplier_objects_for_message(
            from_addr, to_addr, subject)

        # load quotes from the file into the database
        self.logger.info('Matched email with supplier: %s' % supplier.name)

        attachments = get_attachments(message)
        if len(attachments) == 0:
            self.logger.warn(
                'Email from %s has no attachments' % supplier.name)
        for file_name, file_content in attachments:
            if (supplier.matrix_file_name is not None
                and not re.match(supplier.matrix_file_name, file_name)):
                self.logger.warn(
                    ('Skipped attachment from %s with unexpected '
                    'name: "%s"') % (supplier.name, file_name))
                continue

            self.logger.info('Processing attachment from %s: "%s"' % (
                supplier.name, file_name))
            self._quote_dao.begin_nested()
            try:
                count = self._process_quote_file(supplier, altitude_supplier,
                                                 file_content)
            except:
                self._quote_dao.rollback()
                raise
            self._quote_dao.commit()
            self.logger.info('Read %s quotes for %s from "%s"' % (
                supplier.name, count, file_name))

        self.logger.info('Finished email from %s' % supplier)

