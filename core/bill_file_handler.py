#!/usr/bin/python
import hashlib

from billing.core.model import UtilBill


class BillFileHandler(object):
    '''This class handles everything related to utility bill files, which are
    stored in Amazon S3.
    '''
    HASH_CHUNK_SIZE = 1024 ** 2

    def __init__(self, connection, bucket_name, utilbill_loader, url_format):
        ''':param connection: boto.s3.S3Connection
        :param bucket_name: name of S3 bucket where utility bill files are
        :param url_format: format string for URL where utility bill files can
        be accessed, e.g.
        "https://s3.amazonaws.com/%(bucket_name)s/utilbill/%(key_name)s"
        (must be formattable with a dict having "bucket_name" and "key_name"
        keys).
        '''
        self._connection = connection
        self._bucket_name = bucket_name
        self._utilbill_loader = utilbill_loader
        self._url_format = url_format

    @classmethod
    def compute_hexdigest(cls, file):
        '''Return SHA-256 hash of the given file (must be seekable).
        '''
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
    def _get_key_name(utilbill):
        return 'utilbill/' + utilbill.sha256_hexdigest

    def _get_amazon_bucket(self):
        return self._connection.get_bucket(self._bucket_name)

    def get_s3_url(self, utilbill):
        '''Return a URL to access the file corresponding to the given utility
        bill. Return empty string for a UtilBill that has no file or whose
        sha256_hexdigest is None or "".
        '''
        # some bills have no file and therefore no URL
        if utilbill.state > UtilBill.Complete:
            return ''
        # some utility bills lack a file even they're supposed to due to bad
        # data. see https://skylineinnovations.atlassian.net/browse/BILL-5744
        if utilbill.sha256_hexdigest in (None, ''):
            return ''
        return self._url_format % dict(bucket_name=self._bucket_name,
                                      key_name=self._get_key_name(utilbill))

    def delete_utilbill_pdf_from_s3(self, utilbill):
        """Removes the pdf file associated with utilbill from s3 (unless
        there are any other UtilBills referring to the same file).
        """
        # TODO: fail if count is not 1?
        if self._utilbill_loader.count_utilbills_with_hash(
                utilbill.sha256_hexdigest) == 1:
            key_name = BillFileHandler._get_key_name(utilbill)
            key = self._get_amazon_bucket().get_key(key_name)
            key.delete()

    def upload_utilbill_pdf_to_s3(self, utilbill, file):
        """Uploads the pdf file to amazon s3
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file: a seekable file
        """
        utilbill.sha256_hexdigest = BillFileHandler.compute_hexdigest(file)
        key_name = self._get_key_name(utilbill)
        key = self._get_amazon_bucket().new_key(key_name)
        key.set_contents_from_file(file)

