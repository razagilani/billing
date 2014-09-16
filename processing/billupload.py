#!/usr/bin/python
import hashlib
from boto.s3.connection import S3Connection
import os
from billing import config
from billing.processing.state import Session, UtilBill

class BillUpload(object):

    def __init__(self, connection):
        ''':param connection: boto.s3.S3Connection
        '''
        self._connection = connection

    @staticmethod
    def compute_hexdigest(data):
        hash_function = hashlib.sha256()
        hash_function.update(data)
        return hash_function.hexdigest()

    @staticmethod
    def _get_key_name(utilbill):
        return os.path.join('utilbill', utilbill.sha256_hexdigest)

    def _get_amazon_bucket(self):
        return self._connection.get_bucket(config.get('bill', 'bucket'))

    def _upload_to_s3(self, key_name, file_data):
        """Uploads file_data to the key given by key_name"""
        key = self._get_amazon_bucket().new_key(key_name)
        key.set_contents_from_string(file_data)

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

    def upload_utilbill_pdf_to_s3(self, utilbill, file_io):
        """Uploads the pdf file to amazon s3
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file_io: a RawIO file
        """
        file_data = file_io.read()
        utilbill.sha256_hexdigest = BillUpload.compute_hexdigest(file_data)
        key_name = self._get_key_name(utilbill)
        self._upload_to_s3(key_name, file_data)

    # TODO: this should go away when recent changes are merged
    def get_reebill_file_path(self, account, sequence):
        """Return the path for the PDF file of the reebill given by account,
        sequence.
        """
        return os.path.join(config.get('bill', 'billpath'),
                            account, '%s_%.4d.pdf' % (account, sequence))
