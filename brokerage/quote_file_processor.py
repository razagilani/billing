from cStringIO import StringIO
import email
from itertools import islice
import logging
import os
import re
import traceback
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from brokerage.brokerage_model import Company, CompanyPGSupplier
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


class QuoteEmailProcessor(object):
    """Receives emails from suppliers containing matrix quote files as
    attachments, and extracts the quotes from the attachments.
    """
    # maps each supplier primary key to the class for parsing its quote file
    CLASSES_FOR_SUPPLIERS = {
        14: quote_parsers.DirectEnergyMatrixParser,
        95: quote_parsers.AEPMatrixParser,
        199: quote_parsers.USGEMatrixParser,
    }

    # number of quotes to read and insert at once. larger is faster as long
    # as it doesn't use up too much memory. (1000 is the maximum number of
    # rows allowed per insert statement in pymssql.)
    BATCH_SIZE = 1000

    def __init__(self):
        self.logger = logging.getLogger(LOG_NAME)
        self.altitude_session = AltitudeSession()

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
        quote_parser = self.CLASSES_FOR_SUPPLIERS[supplier.id]()
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
            self.altitude_session.bulk_save_objects(quote_list)
            # TODO: probably not a good way to find out that the parser is done
            if quote_list == []:
                break
            self.logger.debug('%s quotes so far' % quote_parser.get_count())
            self.altitude_session.commit()

    def process_email(self, email_file):
        """Read an email from the given file, which should be an email from a
        supplier containing one or more matrix quote files as attachments.
        Determine which supplier the email is from, and process each
        attachment using a QuoteParser to extract quotes from the file and
        restore them in the Altitude database.
        :param email_file: text file with the full content of an email
        """
        try:
            message = email.message_from_file(email_file)
            from_addr, to_addr = message['From'], message['To']
            subject = message['Subject']
            if None in (from_addr, to_addr, subject):
                raise EmailError('Invalid email format')

            q = Session().query(Supplier).filter(
                or_(Supplier.matrix_email_sender == None,
                    Supplier.matrix_email_sender.like(from_addr)),
                or_(Supplier.matrix_email_recipient == None,
                    Supplier.matrix_email_recipient.like(to_addr)),
                or_(Supplier.matrix_email_subject == None,
                    Supplier.matrix_email_subject.like(subject)))
            try:
                supplier = q.one()
            except (NoResultFound, MultipleResultsFound) as e:
                raise UnknownSupplierError

            # match supplier in Altitude database by name--this means names
            # for the same supplier must always be the same (will be None if
            # not found)
            q = self.altitude_session.query(
                Company).filter_by(name=supplier.name)
            try:
                altitude_supplier = q.one()
            except (NoResultFound, MultipleResultsFound) as e:
                raise UnknownSupplierError

            # load quotes from the file into the database
            self.logger.info('Starting to read quotes from %s' % supplier.name)

            attachments = get_attachments(message)
            if len(attachments) == 0:
                self.logger.warn(
                    'Email from %s has no attachments' % supplier.name)
            for file_name, file_content in attachments:
                if (supplier.matrix_file_name is not None
                    and not re.match(supplier.matrix_file_name, file_name)):
                    self.logger.warn(
                        ('Skipped attachment attacment from %s with unexpected '
                        'name: "%s"') % (supplier.name, file_name))
                    continue
                self.logger.info(
                    'Processing file from %s: "%s' % (supplier.name, file_name))
                count = self._process_quote_file(supplier, altitude_supplier,
                                                file_content)
        except Exception as e:
            self.logger.error('Error when processing email:\n%s' % (
                traceback.format_exc()))
            self.altitude_session.rollback()
        else:
            self.logger.info('Read %s quotes from "%s"' % (
                count, supplier.name))
        Session.remove()
        AltitudeSession.remove()

