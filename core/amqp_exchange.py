import json
from boto.s3.connection import S3Connection
from formencode.validators import String, Regex, FancyValidator
from formencode import Schema
from formencode.api import Invalid
from formencode.foreach import ForEach
from datetime import datetime
import re
import pika

from billing.core.bill_file_handler import BillFileHandler
from billing.core.model import Session, Address, UtilityAccount
from billing.core.altitude import AltitudeUtility, get_utility_from_guid, \
    AltitudeGUID, update_altitude_account_guids
from billing.exc import AltitudeDuplicateError
from billing.core.pricing import FuzzyPricingModel
from billing.core.utilbill_loader import UtilBillLoader
from billing.reebill.utilbill_processor import UtilbillProcessor


class DueDateValidator(FancyValidator):
    ''' Validator for "due_date" field in utility bill
    messages. ISO-8601 datetime string or empty string converted to Date or None
    '''

    def _convert_to_python(self, value, state):
        try:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # Parse Errors are considered TypeErrors
            return Invalid('Could not parse "due_date" string: %s' % value)
        return None if value == '' else dt.date()


class TotalValidator(FancyValidator):
    '''Validator for the odd format of the "total" field in utility bill
    messages: dollars and cents as a string preceded by "$", or empty.
    '''
    def _convert_to_python(self, value, state):
        substr = re.match('^\$\d*\.?\d{1,2}|$', value).group(0)
        if substr is None:
            raise Invalid('Invalid "total" string: "%s"' % value, value, state)
        return None if substr == '' else float(substr[1:])

class UtilbillMessageSchema(Schema):
    '''Formencode schema for validating/parsing utility bill message contents.
    specification is at
    https://docs.google.com/a/nextility.com/document/d
    /1u_YBupWZlpVr_vIyJfTeC2IaGU2mYZl9NoRwjF0MQ6c/edit
   '''
    utility_account_number = String()
    utility_provider_guid = Regex(regex=AltitudeGUID.REGEX)
    sha256_hexdigest = Regex(regex=BillFileHandler.HASH_DIGEST_REGEX)
    due_date = DueDateValidator()
    total = TotalValidator()
    service_address = String()
    account_guids = ForEach(Regex(regex=AltitudeGUID.REGEX))


def create_dependencies():
    '''Return objects used for processing AMQP messages to create UtilBills
    and Utilities: pika.connection.Connection, pika.channel.Channel,
    exchange name (string), queue name (string), and UtilbillProcessor.

    This can be called by both run_amqp_consumers.py and test code.
    '''
    from billing import config
    host_name = config.get('amqp', 'host')
    exchange_name = config.get('amqp', 'exchange')
    queue_name = config.get('amqp', 'utilbill_queue')

    s3_connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                 config.get('aws_s3', 'aws_secret_access_key'),
                                 is_secure=config.get('aws_s3', 'is_secure'),
                                 port=config.get('aws_s3', 'port'),
                                 host=config.get('aws_s3', 'host'),
                                 calling_format=config.get('aws_s3',
                                                           'calling_format'))
    utilbill_loader = UtilBillLoader(Session())
    url_format = 'http://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
        config.get('aws_s3', 'host'), config.get('aws_s3', 'port'))
    bill_file_handler = BillFileHandler(s3_connection,
                                        config.get('aws_s3', 'bucket'),
                                        utilbill_loader, url_format)
    rabbitmq_connection = pika.BlockingConnection(
        pika.ConnectionParameters(host_name))
    channel = rabbitmq_connection.channel()
    channel.exchange_declare(exchange=exchange_name)
    channel.queue_declare(queue=queue_name)
    channel.queue_bind(exchange=exchange_name, queue=queue_name)

    s = Session()
    utilbill_loader = UtilBillLoader(s)
    pricing_model = FuzzyPricingModel(utilbill_loader)
    utilbill_processor = UtilbillProcessor(pricing_model, bill_file_handler, None)
    return (rabbitmq_connection, channel, exchange_name, queue_name,
            utilbill_processor)

# TODO: this code is not used yet (and not tested). it was originally decided
#  that it was necessary to synchronize utilities between altitude and
# billing databases, but this was later un-decided, so nothing is being done
# about it for now. see BILL-3784.
def consume_utility_guid(channel, queue_name, utilbill_processor):
    '''Register callback for AMQP messages to receive a utility.
    '''
    def callback(ch, method, properties, body):
        try:
            d = json.loads(body)
            name, guid = d['name'], d['utility_provider_guid']

            # TODO: this may not be necessary because unique constraint in the
            # database can take care of preventing duplicates
            s = Session()
            if s.query(AltitudeUtility).filter_by(guid=guid).count() != 0:
                raise AltitudeDuplicateError(
                    'Altitude utility "%" already exists with name "%s"' % (
                        guid, name))

            new_utility = utilbill_processor.create_utility(name)
            s.add(AltitudeUtility(new_utility, guid))
            s.commit()
        except:
            ch.basic_ack()
            raise
    channel.basic_consume(callback, queue=queue_name)
    channel.start_consuming()

def consume_utilbill_file(channel, queue_name, utilbill_processor):
    '''Register callback for AMQP messages to receive a utility bill.
    '''
    def callback(ch, method, properties, body):
        try:
            d = UtilbillMessageSchema.to_python(json.loads(body))
            s = Session()
            utility = get_utility_from_guid(d['utility_provider_guid'])
            utility_account = s.query(UtilityAccount).filter_by(
                account_number=d['utility_account_number']).one()
            sha256_hexdigest = d['sha256_hexdigest']
            total = d['total']
            due_date = d['due_date']
            service_address_street = d['service_address']
            account_guids = d['account_guids']

            utilbill_processor.create_utility_bill_with_existing_file(
                utility_account, utility, sha256_hexdigest,
                target_total=total,
                service_address=Address(street=service_address_street),
                due_date=due_date)
            update_altitude_account_guids(utility_account, account_guids)
            s.commit()
        except:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            raise
    channel.basic_consume(callback, queue=queue_name)
    channel.start_consuming()

