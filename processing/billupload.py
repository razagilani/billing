#!/usr/bin/python
import hashlib
from boto.s3.connection import S3Connection
import os
from billing import config
from billing.processing.state import Session, UtilBill

class BillUpload(object):

    @staticmethod
    def compute_hexdigest(data):
        hash_function = hashlib.sha256()
        hash_function.update(data)
        return hash_function.hexdigest()

    @staticmethod
    def get_amazon_bucket():
        connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                              config.get('aws_s3', 'aws_secret_access_key'),
                              is_secure=config.get('aws_s3', 'is_secure'),
                              port=config.get('aws_s3', 'port'),
                              host=config.get('aws_s3', 'host'),
                              calling_format=config.get('aws_s3',
                                                        'calling_format'))
        return connection.get_bucket(config.get('bill', 'bucket'))

    @staticmethod
    def utilbill_key_name(utilbill):
        return os.path.join('utilbill', utilbill.sha256_hexdigest)

    @staticmethod
    def upload_to_s3(key_name, file_data):
        """Uploads file_data to the key given by key_name"""
        key = BillUpload.get_amazon_bucket().new_key(key_name)
        key.set_contents_from_string(file_data)

    @staticmethod
    def delete_utilbill_pdf_from_s3(utilbill):
        """Removes the pdf file associated with utilbill from s3"""
        hexdigest = utilbill.sha256_hexdigest
        session = Session()
        if session.query(UtilBill).\
            filter_by(sha256_hexdigest=utilbill.sha256_hexdigest).count() == 1:
            key_name = BillUpload.utilbill_key_name(utilbill)
            key = BillUpload.get_amazon_bucket().get_key(key_name)
            key.delete()

    @staticmethod
    def upload_utilbill_pdf_to_s3(utilbill, file_io):
        """Uploads the pdf file to amazon s3
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file_io: a RawIO file
        """
        file_data = file_io.read()
        utilbill.sha256_hexdigest = BillUpload.compute_hexdigest(file_data)
        key_name = BillUpload.utilbill_key_name(utilbill)
        BillUpload.upload_to_s3(key_name, file_data)

    @staticmethod
    def get_reebill_file_path(account, sequence):
        """Return the path for the PDF file of the reebill given by account,
        sequence.
        """
        return os.path.join(config.get('bill', 'billpath'),
                            account, '%s_%.4d.pdf' % (account, sequence))
