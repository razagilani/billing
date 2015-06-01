from boto.s3.connection import S3Connection
from celery.bin import celery
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Main
from core.utilbill_loader import UtilBillLoader

from core import initialize
initialize()
from core import celery

def _create_main():
    from core import config
    s3_connection = S3Connection(
        config.get('aws_s3', 'aws_access_key_id'),
        config.get('aws_s3', 'aws_secret_access_key'),
        is_secure=config.get('aws_s3', 'is_secure'),
        port=config.get('aws_s3', 'port'),
        host=config.get('aws_s3', 'host'),
        calling_format=config.get('aws_s3', 'calling_format'))
    url_format = 'http://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
        config.get('aws_s3', 'host'), config.get('aws_s3', 'port'))
    bfh = BillFileHandler(s3_connection, config.get('aws_s3', 'bucket'),
                          UtilBillLoader(), url_format)
    return Main(bfh)

@celery.task
def extract_bill(utilbill_id):
    """Extract a bill.
    :param utilbill_id: primary key of UtilBill to extract.
    """
    # TODO: the same Main object could be shared by all tasks
    main = _create_main()
    main.extract(utilbill_id)
