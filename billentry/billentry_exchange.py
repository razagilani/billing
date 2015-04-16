import logging
from core.altitude import AltitudeGUID
from mq import MessageHandler, MessageHandlerManager, REJECT_MESSAGE
from pika import URLParameters
from sqlalchemy.orm.exc import NoResultFound
from voluptuous import Schema, Match
from billentry import common
from core.model import Session, UtilBill
from mq.schemas.validators import MessageVersion
from core import altitude

__all__ = [
    'consume_utilbill_guids_mq',
]

LOG_NAME = 'amqp_utilbill_guids_file'

UtilbillMessageSchema = Schema({
    'guid': Match(AltitudeGUID.REGEX),
    'message_version': MessageVersion(1)
}, required=True)

def create_amqp_conn_params():
    '''Return objects used for processing AMQP messages to create UtilBills
    and Utilities: pika.connection.Connection, pika.channel.Channel,
    exchange name (string), queue name (string), and UtilbillProcessor.

    This can be called by both run_amqp_consumers.py and test code.
    '''
    from core import config
    exchange_name = config.get('amqp', 'exchange')
    routing_key = config.get('amqp', 'utilbill_guids_routing_key')

    amqp_connection_parameters = URLParameters(config.get('amqp', 'url'))

    return (exchange_name, routing_key, amqp_connection_parameters)


class ConsumeUtilbillGuidsHandler(MessageHandler):
    on_error = REJECT_MESSAGE

    # instead of overriding the 'validate' method of the superclass, a class
    # variable is set which is used there to check that incoming messages
    # conform to the schema.
    message_schema = UtilbillMessageSchema

    def __init__(self, exchange_name, routing_key, connection_parameters,
            core_altitude_module=None, billentry_common_module=None):
        '''Note: AMQP connection parameters are stored inside the superclass'
        __init__, but a connection is not actually created until you call
        connect(), not in __init__. So it is not possible to fully unit test
        the class using a mock connection, but it is possible to instantiate
        the class in unit tests and call methods that don't actually use the
        connection--the most important ones being 'validate' and 'handle'.
        '''
        super(ConsumeUtilbillGuidsHandler, self).__init__(
            exchange_name, routing_key, connection_parameters)
        self.core_altitude_module = core_altitude_module
        self.billentry_common_module = billentry_common_module

    def handle(self, message):
        logger = logging.getLogger(LOG_NAME)
        logger.debug("Got message: can't print it because datetime.date is not "
                     "JSON-serializable")
        guid = message['guid']
        try:
            utilbill = self.core_altitude_module.get_utilbill_from_guid(guid)
            if utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY:
                self.billentry_common_module.\
                    replace_utilbill_with_beutilbill(utilbill)
                Session().commit()
        except NoResultFound:
            logger.error('Utility Bill for guid %s not found' % guid)
            raise

def consume_utilbill_guids_mq(
        exchange_name, routing_key, amqp_connection_parameters):
    '''Block to wait for messages about utility bill guids and
    process them by creating new BEUtilBill.
    '''
    def consume_utilbill_guids_handler_factory():
        return ConsumeUtilbillGuidsHandler(
            exchange_name, routing_key, amqp_connection_parameters,
            core_altitude_module=altitude, billentry_common_module=common)
    mgr = MessageHandlerManager(amqp_connection_parameters)
    mgr.attach_message_handler(exchange_name, routing_key,
                               consume_utilbill_guids_handler_factory)
    mgr.run()