from cStringIO import StringIO
import email
from itertools import islice
import logging
import re
import traceback

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
import statsd

from core.model import AltitudeSession, Session, Supplier
from core.exceptions import BillingError
from util.email_util import get_attachments
from brokerage.brokerage_model import Company

LOG_NAME = 'read_quotes'

# names used for metrics submitted to StatsD: quotes by supplier and total
# emails.
# when no StatsD server is running (e.g. while testing) nothing happens
QUOTE_METRIC_FORMAT = 'quote.matrix.%(suppliername)s'
EMAIL_METRIC_NAME = 'quote.email'

class QuoteProcessingError(BillingError):
    pass

class EmailError(QuoteProcessingError):
    """Email was invalid.
    """

class UnknownSupplierError(QuoteProcessingError):
    """Could not match an email to a supplier, or more than one supplier
    matched it.
    """

class UnknownFormatError(QuoteProcessingError):
    """Could not match a file a matrix format, or more than one format
    matched it.
    """

class NoFilesError(QuoteProcessingError):
    """There were no attachments or all were skipped."""

class NoQuotesError(QuoteProcessingError):
    """No quotes were read."""

class MultipleErrors(QuoteProcessingError):
    """Used to report a series of one or more error messages from processing
    multiple files.
    """
    def __init__(self, file_count, messages):
        """
        :param messages: list of (Exception, stack trace string) tuples
        """
        super(QuoteProcessingError, self).__init__()
        self.file_count = file_count
        self.messages = messages

    def __str__(self):
        return '%s files processed, %s errors:\n\n%s' % (
            self.file_count, len(self.messages), '\n'.join(self.messages))


class QuoteDAO(object):
    """Handles database access for QuoteEmailProcessor. Not sure if it's a
    good design to wrap the SQLAlchemy session object like this.
    """
    def __init__(self):
        self.altitude_session = AltitudeSession()

    def get_supplier_objects_for_message(self, to_addr):
        """Determine which supplier an email is from using the recipient's
        email address. This works because emails containing matrices are
        forwarded to a unique address for each supplier.

        Raise UnknownSupplierError if there was not exactly one supplier
        corresponding to the email in the main database, and another with the
        same name in the Altitude database.

        :param from_addr: regular expression string for email sender address

        :return: core.model.Supplier representing the supplier table int the
        main database, brokerage.brokerage_model.Company representing the
        same supplier in the Altitude database (may be None).
        """
        # the matching behavior is implemented by counting the number of
        # matching suppliers for each criterion, and then only filtering by that
        # criterion if the count > 0. i couldn't think of a way that avoids
        # doing multiple queries.
        s = Session()
        q = s.query(Supplier).filter_by(matrix_email_recipient=to_addr)
        count = q.count()
        try:
            supplier = q.one()
        except (NoResultFound, MultipleResultsFound):
            raise UnknownSupplierError(
                '%s suppliers matched recipient address %s' % (count, to_addr))

        # match supplier in Altitude database by name--this means names
        # for the same supplier must always be the same
        q = self.altitude_session.query(Company).filter_by(name=supplier.name)
        altitude_supplier = q.first()
        return supplier, altitude_supplier

    def get_matrix_format_for_file(self, supplier, file_name):
        """
        Return the MatrixFormat object that determines which parser class will
        be used to parse a file from the given supplier with the given name.

        The chosen MatrixFormat is the one whose matrix attachment name
        (regular expression) matches the file name (case-insensitive), or whose
        matrix attachment name is None. This should be unique.
        UnknownFormatError is raised if there is not exactly one match.

        :param supplier: core.model.Supplier
        :param file_name: name of the matrix file
        :return: brokerage.brokerage_model.MatrixFormat
        """
        matching_formats = [f for f in supplier.matrix_formats
                            if f.matrix_attachment_name is None
                            or re.match(f.matrix_attachment_name, file_name,
                                        re.IGNORECASE | re.DOTALL)]
        if len(matching_formats) == 0:
            raise UnknownFormatError('No formats matched file name "%s"' %
                                     file_name)
        if len(matching_formats) > 1:
            raise UnknownFormatError('Multiple formats matched file name '
                                     '"%s"' % file_name)
        return matching_formats[0]

    def insert_quotes(self, quote_list):
        """
        Insert Quotes into the Altitude database, using the SQLAlchemy "bulk
        insert" feature for performance.
        :param quote_list: iterable of Quote objects
        """
        self.altitude_session.bulk_save_objects(quote_list)

    def begin(self):
        """Start transaction in Altitude database for one quote file.
        (Temporary replacement for begin_nested which works on Postgres but
        hasn't been working on SQL server.)
        """
        # there is nothing to do because a transaction always exists.
        pass

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


class QuoteEmailProcessor(object):
    """Receives emails from suppliers containing matrix quote files as
    attachments, and extracts the quotes from the attachments.
    """
    # number of quotes to read and insert at once. larger is faster as long
    # as it doesn't use up too much memory. (1000 is the maximum number of
    # rows allowed per insert statement in pymssql.)
    BATCH_SIZE = 1000

    def __init__(self, classes_for_formats, quote_dao, s3_connection,
                 s3_bucket_name):
        """
        :param classes_for_formats: dictionary mapping the primary key of
        each MatrixFormat in the database to the QuoteParser subclass that
        handles it.
        :param quote_dao: QuoteDAO object for handling database access.
        param s3_connection: boto.s3.S3Connection
        :param bucket_name: name of S3 bucket where quote files will be
        stored (string).
        """
        self.logger = logging.getLogger(LOG_NAME)
        self.logger.setLevel(logging.DEBUG)
        self._classes_for_formats = classes_for_formats
        self._quote_dao = quote_dao
        self._s3_connection = s3_connection
        self._s3_bucket_name = s3_bucket_name

    def _process_quote_file(self, supplier, altitude_supplier, file_name,
                            file_content):
        """Process quotes from a single quote file for the given supplier.

        :param supplier: core.model.Supplier instance

        :param altitude_supplier: brokerage.brokerage_model.Company instance
        corresponding to the Company table in the Altitude SQL Server database,
        representing a supplier. Not to be confused with the "supplier" table
        (core.model.Supplier) or core.altitude.AltitudeSupplier which is a
        mapping between these two. May be None if the supplier is unknown.

        :param file_name: name of quote file (can be used to get the date)

        :param file_content: content of a quote file as a string. (A file
        object would be better, but the Python 'email' module processes a
        whole file at a time so it all has to be in memory anyway.)

        :return the QuoteParser instance used to process the given file (
        which can be used to get the number of quotes).
        """
        # find the MatrixFormat corresponding to this file
        # (may raise UnknownFormatError)
        matrix_format = self._quote_dao.get_matrix_format_for_file(
            supplier, file_name)

        # upload files after identifying the format, but before parsing,
        # so even invalid files get uploaded
        self._store_quote_file(file_name, file_content)

        # copy string into a StringIO :(
        quote_file = StringIO(file_content)

        # pick a QuoteParser class for the given supplier, and load the file
        # into it, and validate the file
        quote_parser = self._classes_for_formats[
            matrix_format.matrix_format_id]()
        quote_parser.load_file(quote_file, file_name=file_name)
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
            if quote_list == []:
                return quote_parser
            self.logger.debug('%s quotes so far' % count)

    def _store_quote_file(self, file_name, file_content):
        """Upload the file content to the S3 bucket as a key with the given
        name.
        :param file_name: name of the file (string)
        :param file_content: content of the file (string)
        """
        bucket = self._s3_connection.get_bucket(self._s3_bucket_name)
        key = bucket.new_key(file_name)
        key.set_contents_from_string(file_content)

    def process_email(self, email_file):
        """Read an email from the given file, which should be an email from a
        supplier containing one or more matrix quote files as attachments.
        Determine which supplier the email is from, and process each
        attachment using a QuoteParser to extract quotes from the file and
        store them in the Altitude database.

        If there are no attachments, nothing happens.

        Quotes should be inserted with a savepoint after each file is
        completed, so an error in a later file won't affect earlier ones. But
        for now we are using one transaction per file.
        TODO: get savepoints working on SQL Server.

        Raise EmailError if something went wrong with the email.
        Raise UnknownSupplierError if there was not exactly one supplier
        corresponding to the email in the main database and another with the
        same name in the Altitude database.
        Raise ValidationError if there was a problem with a quote file
        itself or the quotes in it.

        :param email_file: text file with the full content of an email
        """
        self.logger.info('Starting to read email')
        email_counter = statsd.Counter(EMAIL_METRIC_NAME)
        email_counter += 1

        message = email.message_from_file(email_file)
        from_addr, to_addr = message['From'], message['Delivered-To']
        subject = message['Subject']
        if None in (from_addr, to_addr, subject):
            raise EmailError('Invalid email format')

        supplier, altitude_supplier = \
            self._quote_dao.get_supplier_objects_for_message(to_addr)

        # load quotes from the file into the database
        self.logger.info('Matched email with supplier: %s' % supplier.name)

        attachments = get_attachments(message)
        # TODO: should 0 attachments be considered an error?
        if len(attachments) == 0:
            self.logger.warn(
                'Email from %s has no attachments' % supplier.name)

        # since an exception when processing one file causes that file to be
        # skipped, but other files are still processed, error messages must
        # be stored so they can be reported after all files have been processed.
        # to avoid complexity this is done even if there was only one error.
        error_messages = []

        files_count, quotes_count = 0, 0
        for file_name, file_content in attachments:
            self.logger.info('Processing attachment from %s: "%s"' % (
                supplier.name, file_name))
            self._quote_dao.begin()
            try:
                quote_parser = self._process_quote_file(
                    supplier, altitude_supplier, file_name, file_content)
            except UnknownFormatError:
                self._quote_dao.rollback()
                self.logger.warn(('Skipped attachment from %s with unexpected '
                                 'name: "%s"') % (supplier.name, file_name))
                continue
            except Exception as e:
                self._quote_dao.rollback()
                message = 'Error when processing attachment "%s":\n%s' % (
                    file_name, traceback.format_exc())
                # TODO: is logging this here redundant?
                self.logger.error(message)
                error_messages.append(message)
                continue
            self._quote_dao.commit()
            quotes_count = quote_parser.get_count()
            self.logger.info('Read %s quotes for %s from "%s"' % (
                quotes_count, supplier.name, file_name))
            quotes_counter = statsd.Counter(QUOTE_METRIC_FORMAT % dict(
                suppliername=quote_parser.NAME))
            # submit metric
            quotes_counter += quotes_count
            files_count += 1

        if len(error_messages) > 0:
            raise MultipleErrors(len(attachments), error_messages)

        # if all files were skipped, or at least one file was read but 0
        # quotes were in them, it's considered an error
        if files_count == 0:
            raise NoFilesError('No files were read')
        elif quotes_count == 0:
            raise NoQuotesError('Files contained no quotes')

        self.logger.info('Finished email from %s' % supplier)
        AltitudeSession.remove()

