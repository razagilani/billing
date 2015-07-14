import hashlib
import string

from core.model import UtilBill
from exc import MissingFileError, DuplicateFileError

class BillFileHandler(object):
    """Handles everything related to utility bill files. These are
    stored in Amazon S3 but the interface is intended to be independent of S3
    so they could potentially be stored anywhere.
    """
    HASH_CHUNK_SIZE = 1024 ** 2

    # for validating file hash strings
    HASH_DIGEST_LENGTH = 64
    HASH_DIGEST_REGEX = '^[0-9a-f]{%s}$' % HASH_DIGEST_LENGTH

    def __init__(self, connection, bucket_name, utilbill_loader, url_format):
        """param connection: boto.s3.S3Connection
        :param bucket_name: name of S3 bucket where utility bill files are
        :param utilbill_loader: UtilBillLoader object to access the utility
        bill database.
        :param url_format: format string for URL where utility bill files can
        be accessed, e.g.
        "https://s3.amazonaws.com/%(bucket_name)s/utilbill/%(key_name)s"
        (must be formattable with a dict having "bucket_name" and "key_name"
        keys).
        """
        self._connection = connection
        self._bucket_name = bucket_name
        self._utilbill_loader = utilbill_loader
        self._url_format = url_format

    @classmethod
    def compute_hexdigest(cls, file):
        """Return SHA-256 hash of the given file (must be seekable).
        :param file: seekable file
        """
        hash_function = hashlib.sha256()
        position = file.tell()
        while True:
            data = file.read(cls.HASH_CHUNK_SIZE)
            hash_function.update(data)
            if data == '':
                break
        file.seek(position)
        return hash_function.hexdigest()

    @staticmethod
    def _get_key_name_for_hash(sha256_hexdigest):
        return sha256_hexdigest + '.pdf'

    @classmethod
    def get_key_name_for_utilbill(cls, utilbill):
        """Return the S3 key name for the file belonging to the given UtilBill.
        """
        return cls._get_key_name_for_hash(utilbill.sha256_hexdigest)

    def _get_amazon_bucket(self):
        return self._connection.get_bucket(self._bucket_name)

    def get_url(self, utilbill):
        """Return a URL to access the file corresponding to the given utility
        bill. Return empty string for a UtilBill that has no file or whose
        sha256_hexdigest is None or "".
        :param utilbill: UtilBill
        """
        # some bills have no file and therefore no URL
        if utilbill.state > UtilBill.Complete:
            return ''
        # some utility bills lack a file even they're supposed to due to bad
        # data. see https://skylineinnovations.atlassian.net/browse/BILL-5744
        if utilbill.sha256_hexdigest in (None, ''):
            return ''
        return self._url_format % dict(bucket_name=self._bucket_name,
                                       key_name=self.get_key_name_for_utilbill(
                                           utilbill))

    def check_file_exists(self, utilbill):
        """Raise MissingFileError if the S3 key corresponding to 'utilbill'
        does not exist.
        """
        key_name = self.get_key_name_for_utilbill(utilbill)
        self.key_exists(key_name)

    def key_exists(self, key_name):
        """Raise MissingFileError if the S3 key
        does not exist.
        """
        key = self._get_amazon_bucket().get_key(key_name)
        if key is None:
            raise MissingFileError('Key "%s" does not exist' % key_name)
        return True


    def write_copy_to_file(self, utilbill, output_file):
        """Write a copy of the given bill's file to 'output_file'. (boto
        doesn't allow directly opening a file corresponding to the S3 key.)
        :param utilbill: UtilBill
        :param output_file: writeable file object
        """
        key_name = self.get_key_name_for_utilbill(utilbill)
        key = self._get_amazon_bucket().get_key(key_name)
        if key is None:
            raise MissingFileError('Key "%s" does not exist' % key_name)
        key.get_contents_to_file(output_file)

    def delete_file(self, utilbill):
        """Remove the file associated with 'utilbill' (unless there are any
        other UtilBills referring to the same file). If for some reason the file
        is already missing (e.g. an earlier attempt to delete file caused a
        transaction rollback after deleting it), nothing happens.
        :param utilbill: UtilBill
        """
        # TODO: fail if count is not 1?
        if self._utilbill_loader.count_utilbills_with_hash(
                utilbill.sha256_hexdigest) == 1:
            key_name = BillFileHandler.get_key_name_for_utilbill(utilbill)
            key = self._get_amazon_bucket().get_key(key_name)
            if key is None:
                # key is already gone
                # TODO: this error should be logged somewhere...
                pass
            else:
                key.delete()

    def upload_file(self, file):
        """Upload the given file to s3.
        :param file: a seekable file
        """
        sha256_hexdigest = BillFileHandler.compute_hexdigest(file)
        if self._utilbill_loader.count_utilbills_with_hash(
                sha256_hexdigest) != 0:
            raise DuplicateFileError('File already exists with hash %s ' %
                                     sha256_hexdigest)
        key_name = self._get_key_name_for_hash(sha256_hexdigest)
        key = self._get_amazon_bucket().new_key(key_name)
        key.set_contents_from_file(file)
        return sha256_hexdigest

    def upload_file_for_utilbill(self, utilbill, file):
        """Upload the given file to s3, and also set the
        'UtilBill.sha256_hexdigest' attribute according to the file.
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file: a seekable file
        """
        utilbill.sha256_hexdigest = self.upload_file(file)

