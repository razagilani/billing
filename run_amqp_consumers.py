'''Entry point for AMQP consumers. All config file reading and instantiation of
objects based on config file values should be done here. The substantive code
that actually does things is in core/amqp_exchange.py.
'''
from boto.s3.connection import S3Connection
import pika
from billing import init_config, init_model, init_logging
from billing.reebill.utilbill_processor import UtilbillProcessor
from billing.core.utilbill_loader import UtilBillLoader
from billing.core.pricing import FuzzyPricingModel
from billing.core.amqp_exchange import consume_utilbill_file, \
    consume_utility_guid
from billing.core.model import Session
from billing.core.bill_file_handler import BillFileHandler

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()
    from billing import config

    host_name = config.get('amqp', 'host')
    exchange_name = config.get('amqp', 'exchange')
    queue_name = config.get('amqp', 'utilbill_queue')
    bucket_name = config.get('aws_s3', 'bucket')

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
    utilbill_processor = UtilbillProcessor(pricing_model, bill_file_handler,
                                           None)

    consume_utilbill_file(channel, queue_name, utilbill_processor)
    consume_utility_guid(channel, queue_name, utilbill_processor)
