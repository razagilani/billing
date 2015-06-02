from boto.s3.connection import S3Connection
from celery.bin import celery
from sqlalchemy import desc
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Main, Extractor
from core.model import Session, UtilBill
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

@celery.task(bind=True)
def test_extractor(self, extractor_id, utility_id=None):
    """Test an extractor on all bills.
    """
    s = Session()
    extractor = s.query(Extractor).filter_by(id=extractor_id)
    q = s.query(UtilBill).order_by(desc(UtilBill.date_received))
    if utility_id is not None:
        q = q.filter(UtilBill.utility_id==utility_id)

    for bill in q:
        c = extractor.get_success_count(bill, self._bill_file_handler)

        all_count = self.state.meta.get('all_count', 0)
        any_count = self.state.meta.get('all_count', 0)
        if c > 0:
            any_count += 1
        if c == len(extractor.fields):
            all_count += 1

        # set custom state with process so far
        self.update_state(state='PROGRESS', meta={
            'all_count': all_count,
            'any_count': any_count,
            'total_count': self.state.meta.get('all_count', 0) + 1,
        })
