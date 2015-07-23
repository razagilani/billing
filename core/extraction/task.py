import re
from boto.s3.connection import S3Connection
from celery.exceptions import TaskRevokedError
from celery.result import AsyncResult
from sqlalchemy import func

from core.bill_file_handler import BillFileHandler
from core.extraction import Main, Extractor, ExtractorResult, Applier
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import verify_field
from core.model import Session
from core.model.utilbill import UtilBill
from core.utilbill_loader import UtilBillLoader
from core import init_config, init_celery, init_model


# init_model can't be called here because it will cause a circular import
# with billentry
from core import config
from util.pdf import PDFUtil

if not config:
    del config
    init_config()
    from core import config
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


class DBTask(celery.Task):
    """
    An abstract celery task class that ensures that the database connection is closed after a task completes.
    """
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if status == 'FAILURE':
            print "Error: ", retval
            Session.rollback()
        else:
            Session.commit()
        Session.close()


@celery.task
def extract_bill(utilbill_id):
    """Extract a bill.
    :param utilbill_id: primary key of UtilBill to extract.
    """
    # TODO: the same Main object could be shared by all tasks
    main = _create_main()
    main.extract(utilbill_id)


@celery.task(bind=True, base=DBTask)
def test_bill(self, extractor_id, bill_id):
    '''
    Tests an extractor on a single bill, and returns whether or not it succeeded.

    :param extractor_id: The id of the extractor to apply to the bill
    :param bill_id: The id of the bill to test
    :return: {
        extractor_id, bill_id : the IDs of the current extractor and bill
        num_fields : the total number of fields that should be extracted
        fields : {name:0/1, ...} for each field name in Applier.KEYS.
                Value is 1 if it could be recovered, 0 otherwise
        date : The bill's period end date, read from the database, or if not
        in the database, from the bill.
                If neither succeeds, this is None. 'date' is used to group
                bills by date to see whether formats change over time.
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
    applier_keys = [field.applier_key for field in extractor.fields]
    response = {
        'extractor_id': extractor_id,
        'bill_id': bill_id,
        'num_fields': len(applier_keys),
        'fields': {f:0 for f in applier_keys},
        'fields_correct': {f: 0 for f in applier_keys},
        'fields_incorrect': {f: 0 for f in applier_keys},
    }

    # Store field values for each successful result
    # Note: 'good' is of type {applier_key: value, ...}
    bill_end_date = None
    good, error = extractor.get_values(bill, bill_file_handler)
    for applier_key, value in good.iteritems():
        response['fields'][applier_key] = 1
        if applier_key == UtilBillApplier.END:
            bill_end_date = value

    # get bill period end date from DB, or from extractor
    # this is used to group bills by date and to check for changes over time
    # in format
    if bill.period_end is not None:
        response['date'] = bill.period_end
    elif bill_end_date is not None:
        response['date'] = bill_end_date
    else:
        response['date'] = None

    # compare results to those in the db
    from billentry.billentry_model import BEUtilBill
    response['verified'] = 0
    if (isinstance(bill, BEUtilBill) and bill.is_entered()) or \
            bill.processed:
        if len(good.keys()) > 0:
            response['verified'] = 1
        for applier_key, field_value in good.iteritems():
            db_val = UtilBillApplier.GETTERS[applier_key](bill)
            if not db_val:
                continue

            is_match = verify_field(applier_key, field_value, db_val)
            if is_match:
                response['fields_correct'][applier_key] = 1
            else:
                response['fields_incorrect'][applier_key] = 1
                print "**** VERIFICATION FAILED id: %d, applier key: %s, " \
                      "extracted value: %s, database value: %s" % (bill_id,
                applier_key, field_value, db_val)

    # print out debug information in celery log
    debug = False
    if len(good) != len(extractor.fields) and debug:
        print "\n$$$$$$$"
        print "Extractor Name: ", extractor.name
        print "Bill ID: ", str(bill_id)
        print "Utility: ", bill.utility_id
        print "ERRORS: " + str(len(error))
        print "TEXT LENGTH: ", len(bill.get_text(bill_file_handler,
            PDFUtil()))
        print "*******\n"
    return response


@celery.task(bind=True, base=DBTask)
def reduce_bill_results(self, results):
    '''
    Combines a bunch of results from individual bill tests into one summary.
    Can also commit the results to the database, if it is run as a celery task.
    Note: All results should be from same extractor

    :param results: The set of results to reduce
    :return: response {
        'all_count': number of bills with all fields,
        'any_count': number of bills with at least one field,
        'total_count': total number of bills extracted,
        'verified_count': number of bills verified against DB.
        'fields': success counts for each field, in a dictionary of the form
            { applier_key1: count, ...}
        'fields_fraction': accuracy for each field, in a dictionary of the
            form { applier_key1: count, ...}
        'dates' : dictionary of year-month, each mapping to a copy of 'fields'
            for all bills in the given year & month,
        'failed': number of tasks failed,
        'nbills': number of total bills to be extracted (including ones not yet
        finished)
    }
    '''
    nbills = len(results)
    all_count, any_count, total_count = 0, 0, 0
    verified_count = 0
    failed, stopped = 0, 0
    fields = {}
    # used to compare accuracy of extractor vs what's in the database.
    fields_correct = {}
    fields_incorrect = {}
    fields_fraction = {}
    dates = {}
    results = filter(None, results)
    for r in results:
        # if task failed, then r is in fact an Exception object
        if isinstance(r, TaskRevokedError):
            # if task was manually stopped
            stopped += 1
            continue
        elif isinstance(r, Exception):
            # if task failed for some other reason
            failed += 1
            continue

        # initialize fields hashes with field names
        if not fields.keys():
            fields = {k:0 for k in r['fields'].keys()}
            fields_correct = {k:0 for k in r['fields'].keys()}
            fields_incorrect = {k:0 for k in r['fields'].keys()}
            fields_fraction = {k:0 for k in r['fields'].keys()}

        # use this bill's period_end to add it to the correct date bucket. 
        bill_date = r['date']
        if bill_date is not None:
            bill_date_format = "%04d-%02d" % (bill_date.year, bill_date.month)
        else:
            bill_date_format = "no date"
        if bill_date_format not in dates:
            dates[bill_date_format] = {
                'all_count': 0,
                'any_count': 0,
                'total_count': 0,
                'fields': {key: 0 for key in fields.keys()},
            }

        verified_count += r['verified']

        # count number of successfully read fields
        success_fields = 0
        for k in fields.keys():
            if r['fields'][k]:
                success_fields += 1
                fields[k] += 1
                dates[bill_date_format]['fields'][k] += 1

            # check for each field whether it matches the database
            fields_correct[k] += r['fields_correct'][k]
            fields_incorrect[k] += r['fields_incorrect'][k]

        # Count success for this individual bill
        total_fields = r['num_fields']
        total_count += 1
        dates[bill_date_format]['total_count'] += 1
        if success_fields > 0:
            any_count += 1
            dates[bill_date_format]['any_count'] += 1
        if success_fields == total_fields:
            all_count += 1
            dates[bill_date_format]['all_count'] += 1

    #calculate percent accuracy for each field, relative to the values
    # already in the database

    for k in fields.keys():
        sum = fields_correct[k] + fields_incorrect[k]
        if sum > 0:
            fields_fraction[k] = float(fields_correct[k]) / sum

    response = {
        'nbills': nbills,
        'all_count': all_count,
        'any_count': any_count,
        'total_count': total_count,
        'verified_count': verified_count,
        'failed': failed,
        'stopped': stopped,
        'fields': fields,
        'fields_fraction': fields_fraction,
        'dates': dates,
    }

    from core.model import Session
    if Session.bind is None:
        del Session
        init_model()
        from core.model import Session

    s = Session()
    q = s.query(ExtractorResult).filter(ExtractorResult.task_id == reduce_bill_results.request.id)
    if q.count():
        extractor_result = q.one()
        extractor_result.set_results(response)

    return response

