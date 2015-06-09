from boto.s3.connection import S3Connection
from sqlalchemy import func

from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Main, Applier, Extractor, ExtractorResult
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

class DBTask(celery.Task):
    """
    An abstract celery task class that ensures that the database connection is closed after a task completes.
    """
    abstract=True
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
    s.commit()
    return all_count, any_count, total_count

@celery.task(bind=True, base=DBTask)
def test_bill(self, extractor_id, bill_id):
    '''
    Tests an extractor on a single bill, and returns whether or not it succeeded.

    :param extractor_id: The id of the extractor to apply to the bill
    :param bill_id: The id of the bill to test
    :return: {
        extractor_id, bill_id : the IDs of the current extractor and bill
        num_fields : the total number of fields that should be extracted
        fields : Data for each field. It is of the type {'name1': {'value':###, 'db_match':bool}, 'name2':..., }
                'value' stores the actual retrieved value for each given field name.
                'db_match' is None if the database does not have a value already stored for this field.
                    otherwise, db_match is set to True if the extracted value matches the value in the database, False otherwise.
        date : The bill's period end date, read from the database, or if not in the database, from the bill.
                If neither succeeds, this is None. 'date' is used to group bills by date to see whether formats change over time.
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
    response = {'fields':{key:None for key in Applier.KEYS}}
    response['extractor_id'] = extractor_id
    response['bill_id'] = bill_id
    response['num_fields'] = len(extractor.fields)

    #TODO find better method to get db column from applier key
    getters_map = {
        "charges": lambda x : x.get_total_charges(),
        "end": lambda x : x.period_end,
        "start": lambda x : x.period_start,
        "next read": lambda x : x.get_next_meter_read_date(),
        "energy": lambda x : x.get_total_energy(),
    }

    #TODO right now this is a private method, we should make it public
    # Store field values for each successful result,
    #   as well as whether or not the result matches what's in the database.
    # Note: 'good' is of type [(field, value), ...]
    good, error = extractor._get_values(bill, bill_file_handler)
    for g in good:
        response['fields'][g[0].applier_key] = {'value':str(g[1])}
        db_val = getters_map[g[0].applier_key](bill)
        if db_val:
            if g[1] == db_val:
                response['fields'][g[0].applier_key]['db_match'] = True
            else:
                response['fields'][g[0].applier_key]['db_match'] = False
        else:
            response['fields'][g[0].applier_key]['db_match'] = None

    #get bill period end date from DB, or from extractor
    # this is used to group bills by date and to check for changes over time in format
    if bill.period_end is not None:
        response['date'] = "{:0>4d}-{:0>2d}".format(bill.period_end.year, bill.period_end.month)
    elif response['fields']['end'] is not None:
        response['date'] = response['fields']['end']['value'][:7]
    else:
        response['date'] = ""

    debug = False
    if len(good) != len(extractor.fields) and debug:
        print "\n***"
        print "Extractor Name: ", extractor.name
        print "Bill ID: ", str(bill_id)
        print "Utility: ", bill.utility_id
        for g in good:
            #Compare extracted value to that in the database, to check for false positives.
            db_val = getters_map[g[0].applier_key](bill)
            if db_val and g[1] != db_val:
                print "*** VERIFICATION FAILED ***\t%s\t%s\t%s\tID: %s\n" % (g[0].applier_key, g[1], db_val, bill_id)
                print bill.get_text(bill_file_handler)
        for e in error:
            print "Error: ", e
        print "Text: ", bill.get_text(bill_file_handler)
        print "***\n"

    return response

@celery.task(bind=True)
def reduce_bill_results(self, results, commit=False):
    '''
    Combines a bunch of results from individual bill tests into one summary.
    Can also commit the results to the database, if it is run as a celery task.
    Note: All results should be from same extractor

    :param results: The set of results to reduce
    :return: response {
        'all_count': number of bills with all fields,
        'any_count': number of bills with at least one field,
        'total_count': total number of bills processed,
        'fields': success counts for each field, in a dictionary {name1:{'count', 'db_match', 'db_conflict'}, name2:{...}, ...}
                    'count' stores the number of bills that retrieved the specific field
                    'db_match' stores the number of times the retrieved field matched what was in the database
                    'db_conflict' stores the number of times the retrieved field did *not* match what was in the database
        'dates' : dictionary of year-month, each mapping to a copy of 'fields' for all bills in the given time year & month,
        'failed': number of tasks failed,
        'nbills': number of total bills to be processed (including ones not yet finished)
    }
    '''
    nbills = len(results)
    all_count, any_count, total_count = 0, 0, 0
    dates = {}
    fields = {key:{'count':0, 'db_match':0, 'db_conflict':0} for key in Applier.KEYS}
    results = filter(None, results)
    failed = 0
    for r in results:
        #if task failed, then r is in fact an Error object
        if not isinstance(r, dict):
            failed += 1
            continue

        bill_date = r['date']
        if bill_date not in dates:
            dates[bill_date] = {
                'all_count': 0,
                'any_count': 0,
                'total_count': 0,
                'fields': {key: 0 for key in Applier.KEYS},
            }

        #count number of successfully read fields
        success_fields = 0
        for k in r['fields'].keys():
            if r['fields'][k] is not None:
                success_fields += 1
                fields[k]['count'] += 1
                if r['fields'][k]['db_match'] is not None:
                    if r['fields'][k]['db_match']:
                        fields[k]['db_match'] +=1
                    else:
                        fields[k]['db_conflict'] +=1
                dates[bill_date]['fields'][k] += 1

        #Count success for this individual bill
        total_fields = r['num_fields']
        total_count += 1
        dates[bill_date]['total_count'] += 1
        if success_fields > 0:
            any_count += 1
            dates[bill_date]['any_count'] += 1
        if success_fields == total_fields:
            all_count += 1
            dates[bill_date]['all_count'] += 1

    response =  {
        'all_count': all_count,
        'any_count': any_count,
        'total_count': total_count,
        'fields': fields,
        'dates' : dates,
        'failed': failed,
        'nbills' : nbills,
    }

    if commit:
        s = Session()
        q = s.query(ExtractorResult).filter(ExtractorResult.task_id == reduce_bill_results.request.id)
        extractor_result = q.one()
        extractor_result.set_results(response)
        s.commit()

    return response

@celery.task(bind=True, base=DBTask)
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
    field_count = {f.applier_key:0 for f in extractor.fields}
    for bill in bills:
        #TODO right now this is a private method, we should make it public
        #good is of type [(field, value), ...]
        good, error = extractor._get_values(bill, bill_file_handler)
        c = len(good)
        for g in good:
            field_count[g[0].applier_key] += 1

        if c > 0:
            any_count += 1
        if c == len(extractor.fields) and len(extractor.fields) > 0:
            all_count += 1
        total_count += 1
        self.update_state(state='PROGRESS', meta={
            'all_count': all_count,
            'any_count': any_count,
            'total_count': total_count,
            'fields': field_count,
            # TODO: add count_by_field and count_by_month
        })

    result = s.query(ExtractorResult).filter_by(task_id=self.request.id).one()
    result.set_results(self.request.info)

    return self.request.info
