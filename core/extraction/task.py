from boto.s3.connection import S3Connection
from celery.bin import celery
from celery.result import AsyncResult
from sqlalchemy import desc
from sqlalchemy.sql.expression import nullslast
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Main, Extractor
from core.model import Session, UtilBill
from core.utilbill_loader import UtilBillLoader

from core import init_config, init_celery, init_model

# init_model can't be called here because it will cause a circular import
# with billentry
init_config()
init_celery()
from core import celery

def _create_bill_file_handler():
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
    return BillFileHandler(s3_connection, config.get('aws_s3', 'bucket'),
                          UtilBillLoader(), url_format)

def _create_main():
    bfh = _create_bill_file_handler()
    return Main(bfh)

@celery.task
def extract_bill(utilbill_id):
    """Extract a bill.
    :param utilbill_id: primary key of UtilBill to extract.
    """
    # TODO: the same Main object could be shared by all tasks
    main = _create_main()
    main.extract(utilbill_id)

@celery.task(bind=True)
def test_extractor(self, extractor_id, utility_id=None):
    """Test an extractor on all bills.
    """
    init_model()
    bill_file_handler = _create_bill_file_handler()
    s = Session()
    extractor = s.query(Extractor).filter_by(extractor_id=extractor_id).one()
    q = s.query(UtilBill).order_by(nullslast(desc(UtilBill.date_received)))
    if utility_id is not None:
        q = q.filter(UtilBill.utility_id==utility_id)

    all_count, any_count, total_count = 0, 0, 0
    for bill in q:
        c = extractor.get_success_count(bill, bill_file_handler)
        if c > 0:
            any_count += 1
        if c == len(extractor.fields) and len(extractor.fields) > 0:
            all_count += 1
        total_count += 1

        # set custom state with process so far
        # (i think it's not possible/easy to retrieve the current state
        # metadata after setting it.)
        self.update_state(state='PROGRESS', meta={
            'all_count': all_count,
            'any_count': any_count,
            'total_count': total_count
        })
        print '***** "%s"' % bill.sha256_hexdigest, all_count, any_count, total_count
    return all_count, any_count, total_count
