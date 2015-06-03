from boto.s3.connection import S3Connection
from celery.bin import celery
from celery.result import AsyncResult
from sqlalchemy import desc, func
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
    # init_model() can't be called in global scope because it causes a
    # circular import with Bill Entry. but if init_model is called after it
    # has already been called and data have been inserted (e.g. in a test),
    # the transaction is rolled back and inserted data will be lost. so,
    # only call init_model if it hasn't been called yet.
    from core.model import Session
    if Session.bind is None:
        del Session
        init_model()
        from core.model import Session

    bill_file_handler = _create_bill_file_handler()
    s = Session()
    extractor = s.query(Extractor).filter_by(extractor_id=extractor_id).one()

    # sort bills in random order so partial results show success rates more
    # similar to the final result. bills without file names are excluded
    # because there is no file to extract from.
    q = s.query(UtilBill).filter(UtilBill.sha256_hexdigest != None,
                                 UtilBill.sha256_hexdigest != ''
                                 ).order_by(func.random())
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

@celery.task(bind=True)
def test_bill(self, extractor_id, bill_id):
    '''
    Tests an extractor on a single bill, and returns whether or not it succeeded.

    TODO This function calls init_model() and _create_bill_file_handler().
    I'm not sure if this is a performance issue, or if we can do this once for a whole set of bills.
    I'm not sure how celery handles data sharing between tasks.

    :param extractor: The extractor to apply to the bill
    :param bill: The bill to test
    :return: A dict containing {
                all_count: 1 if all fields were extracted, 0 otherwise
                any_count: 1 if any fields were extracted, 0 otherwise
                total_count: 1
            }
    '''
    from core.model import Session
    if Session.bind is None:
        del Session
        init_model()
        from core.model import Session

    bill_file_handler = _create_bill_file_handler()
    s = Session()
    extractor = s.query(Extractor).filter_by(extractor_id=extractor_id).one()
    bill = s.query(UtilBill).filter_by(id=bill_id).one()
    c = extractor.get_success_count(bill, bill_file_handler)
    all_count, any_count, total_count = 0, 0, 0
    if c > 0:
        any_count = 1
    if c == len(extractor.fields) and len(extractor.fields) > 0:
        all_count = 1
    total_count = 1
    return {
        'all_count': all_count,
        'any_count': any_count,
        'total_count': total_count
    }

@celery.task(bind=True)
def reduce_bill_results(self, results):
    '''
    Combines a bunch of results from individual bill tests into one summary.
    This is done the summing up the all_count, any_count, and total_count fields.
    :param results: The set of results to reduce
    :return: The sum of the fields of the given results.
    '''
    return reduce(lambda r1, r2: {
        'all_count': r1['all_count'] + r2['all_count'],
        'any_count': r1['any_count'] + r2['any_count'],
        'total_count': r1['total_count'] + r2['total_count'],
    }, results)

@celery.task(bind=True)
def test_bills_batch(self, extractor_id, bill_ids):
    from core.model import Session
    if Session.bind is None:
        del Session
        init_model()
        from core.model import Session
    bill_file_handler = _create_bill_file_handler()
    s = Session()
    extractor = s.query(Extractor).filter_by(extractor_id=extractor_id).one()
    bills = s.query(UtilBill).filter(UtilBill.id.in_(bill_ids)).all()

    all_count, any_count, total_count = 0, 0, 0
    for bill in bills:
        c = extractor.get_success_count(bill, bill_file_handler)

        if c > 0:
            any_count += 1
        if c == len(extractor.fields) and len(extractor.fields) > 0:
            all_count += 1
        total_count += 1
        self.update_state(state='PROGRESS', meta={
            'all_count': all_count,
            'any_count': any_count,
            'total_count': total_count
        })

    return {
        'all_count': all_count,
        'any_count': any_count,
        'total_count': total_count
    }