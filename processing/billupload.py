#!/usr/bin/python
import hashlib
from boto.s3.connection import S3Connection
import os
from billing import config
from billing.processing.state import Session, UtilBill

HASH_CHUNK_SIZE = 1024 ** 2

class BillUpload(object):

    def __init__(self, connection):
        ''':param connection: boto.s3.S3Connection
        '''
        self._connection = connection
        self._create_amazon_bucket()

    @classmethod
    def from_config(cls):
        return cls(S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                config.get('aws_s3', 'aws_secret_access_key'),
                                is_secure=config.get('aws_s3', 'is_secure'),
                                port=config.get('aws_s3', 'port'),
                                host=config.get('aws_s3', 'host'),
                                calling_format=config.get('aws_s3',
                                                          'calling_format')))

    @staticmethod
    def compute_hexdigest(file):
        '''Return SHA-256 hash of the given file (must be seekable).
        '''
        hash_function = hashlib.sha256()
        position = file.tell()
        while True:
            data = file.read(HASH_CHUNK_SIZE)
            hash_function.update(data)
            if data == '':
                break
        file.seek(position)
        return hash_function.hexdigest()

    @staticmethod
    def _get_key_name(utilbill):
        return utilbill.sha256_hexdigest

    def _create_amazon_bucket(self):
        self._connection.create_bucket(config.get('bill', 'bucket'))

    def _get_amazon_bucket(self):
        return self._connection.get_bucket(config.get('bill', 'bucket'))

    def delete_utilbill_pdf_from_s3(self, utilbill):
        """Removes the pdf file associated with utilbill from s3.
        """
        session = Session()
        # TODO: fail if count is not 1?
        if session.query(UtilBill).filter_by(
                sha256_hexdigest=utilbill.sha256_hexdigest).count() == 1:
            key_name = BillUpload._get_key_name(utilbill)
            key = self._get_amazon_bucket().get_key(key_name)
            key.delete()

    def upload_utilbill_pdf_to_s3(self, utilbill, file):
        """Uploads the pdf file to amazon s3
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file: a file
        """
        utilbill.sha256_hexdigest = BillUpload.compute_hexdigest(file)
        key_name = self._get_key_name(utilbill)
        key = self._get_amazon_bucket().new_key(key_name)
        key.set_contents_from_file(file)

    # TODO: this should go away when recent changes are merged
    def get_reebill_file_path(self, account, sequence):
        """Return the path for the PDF file of the reebill given by account,
        sequence.
        """
        return os.path.join(config.get('bill', 'billpath'),
                            account, '%s_%.4d.pdf' % (account, sequence))
