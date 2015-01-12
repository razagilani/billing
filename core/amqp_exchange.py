import json
import re
import uuid
from boto.s3.connection import S3Connection
from pika import URLParameters
from datetime import datetime
from sqlalchemy import cast, Integer
from sqlalchemy.orm.exc import NoResultFound
from voluptuous import Schema, Match, Any, Invalid

from billing.reebill.utilbill_processor import UtilbillProcessor
from billing.core.utilbill_loader import UtilBillLoader
from billing.core.pricing import FuzzyPricingModel
from billing.core.bill_file_handler import BillFileHandler
from billing.core.model import Session, Address, UtilityAccount, Utility
from billing.core.altitude import AltitudeUtility, get_utility_from_guid, \
    AltitudeGUID, update_altitude_account_guids
from billing.exc import AltitudeDuplicateError
from mq import MessageHandler, MessageHandlerManager, REJECT_MESSAGE
from mq.schemas.validators import MessageVersion, EmptyString, Date

__all__ = [
    'consume_utilbill_file_mq',
]

# Voluptuous schema for validating/parsing utility bill message contents.
# specification is at
# https://docs.google.com/a/nextility.com/document/d
# /1u_YBupWZlpVr_vIyJfTeC2IaGU2mYZl9NoRwjF0MQ6c/edit

# "voluptuous" convention is to name functions like classes.
def TotalValidator():
    '''Validator for the odd format of the "total" field in utility bill
    messages: dollars and cents as a string preceded by "$", or empty.
    '''
    def validate(value):
        substr = re.match('^\$\d*\.?\d{1,2}|$', value)
        if substr is None:
            raise Invalid('Invalid "total" string: "%s"' % value)
        return None if value == '' else float(substr.group(0)[1:])
    return validate

def DueDateValidator():
    '''Validator for "due_date" field in utility bill messages.
    ISO-8601 datetime string or empty string converted to Date or None.
    '''
    def validate(value):
        if value == '':
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise Invalid('Could not parse "due_date" string: %s' % value)
        return dt.date()
    return validate

UtilbillMessageSchema = Schema({
    'utility_account_number': basestring,
    'sha256_hexdigest': Match(BillFileHandler.HASH_DIGEST_REGEX),
    'due_date': DueDateValidator(),
    'total': TotalValidator(),
    'service_address': basestring,
    'utility_provider_guid': Match(AltitudeGUID.REGEX),
    'account_guids': [basestring],
    'message_version': MessageVersion(1)
}, required=True)


def create_dependencies():
    '''Return objects used for processing AMQP messages to create UtilBills
    and Utilities: pika.connection.Connection, pika.channel.Channel,
    exchange name (string), queue name (string), and UtilbillProcessor.

    This can be called by both run_amqp_consumers.py and test code.
    '''
    from billing import config
    exchange_name = config.get('amqp', 'exchange')
    routing_key = config.get('amqp', 'utilbill_routing_key')

    amqp_connection_parameters = URLParameters(config.get('amqp', 'url'))

    s3_connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                 config.get('aws_s3', 'aws_secret_access_key'),
                                 is_secure=config.get('aws_s3', 'is_secure'),
                                 port=config.get('aws_s3', 'port'),
                                 host=config.get('aws_s3', 'host'),
                                 calling_format=config.get('aws_s3',
                                                           'calling_format'))
    utilbill_loader = UtilBillLoader()
    url_format = 'http://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
        config.get('aws_s3', 'host'), config.get('aws_s3', 'port'))
    bill_file_handler = BillFileHandler(s3_connection, config.get('aws_s3', 'bucket'),
                                        utilbill_loader, url_format)

    utilbill_loader = UtilBillLoader()
    pricing_model = FuzzyPricingModel(utilbill_loader)
    utilbill_processor = UtilbillProcessor(pricing_model, bill_file_handler, None)

    return (exchange_name, routing_key, amqp_connection_parameters,
            utilbill_processor)


class ConsumeUtilbillFileHandler(MessageHandler):
    on_error = REJECT_MESSAGE

    # instead of overriding the 'validate' method of the superclass, a class
    # variable is set which is used there to check that incoming messages
    # conform to the schema.
    message_schema = UtilbillMessageSchema

    def __init__(self, exchange_name, routing_key, connection_parameters,
                 utilbill_processor):
        '''Note: AMQP connection parameters are stored inside the superclass'
        __init__, but a connection is not actually created until you call
        connect(), not in __init__. So it is not possible to fully unit test
        the class using a mock connection, but it is possible to instantiate
        the class in unit tests and call methods that don't actually use the
        connection--the most important ones being 'validate' and 'handle'.
        '''
        super(ConsumeUtilbillFileHandler, self).__init__(
            exchange_name, routing_key, connection_parameters)
        self.utilbill_processor = utilbill_processor

    def handle(self, message):
        s = Session()
        try:
            utility = get_utility_from_guid(message['utility_provider_guid'])
        except NoResultFound:
            raise

        try:
            utility_account = s.query(UtilityAccount).filter_by(
                account_number=message['utility_account_number'],
                fb_utility=utility).one()
        except NoResultFound:
            last_account = s.query(cast(UtilityAccount.account, Integer)).order_by(
                cast(UtilityAccount.account, Integer).desc()).first()
            next_account = str(last_account[0] + 1)
            utility_account = UtilityAccount('', next_account,
                                             utility,
                                             None,
                                             None,
                                             Address(),
                                             Address(street=message['service_address']),
                                             message['utility_account_number']
                                             )
            s.add(utility_account)
        sha256_hexdigest = message['sha256_hexdigest']
        total = message['total']
        due_date = message['due_date']
        service_address_street = message['service_address']
        account_guids = message['account_guids']

        self.utilbill_processor.create_utility_bill_with_existing_file(
            utility_account, utility, sha256_hexdigest,
            target_total=total,
            service_address=Address(street=service_address_street),
            due_date=due_date)
        update_altitude_account_guids(utility_account, account_guids)
        s.commit()


def consume_utilbill_file_mq(
        exchange_name, routing_key, amqp_connection_parameters,
        utilbill_processor):
    '''Block to wait for messages about new utility bill files uploaded to
    S3 and  process them by creating new UtilBills.
    '''
    def consume_utilbill_file_handler_factory():
        return ConsumeUtilbillFileHandler(
            exchange_name, routing_key, amqp_connection_parameters,
            utilbill_processor)
    mgr = MessageHandlerManager(amqp_connection_parameters)
    mgr.attach_message_handler(exchange_name, routing_key,
                               consume_utilbill_file_handler_factory)
    mgr.run()
