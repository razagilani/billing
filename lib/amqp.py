from billing.mq.exchange import Exchange
from billing.mq.publisher import Publisher
from billing.mq.message_handler import MessageHandler

'''
This package contains classes for listening and publishing to an AMQP exchange
using `mq`, a library which Skyline Innovations created for communicating with
an AMQP message broker.


LISTENING:

#Give each handler the name of the routing key it should listen to

def process_color(m):
    print "%s's favorite color is %s!" % (m['name'], m['favorite_color'])

def process_address(message):
    print "%s's address is %s!" % (m['name'], m['address'])

xl = ExchangeListener('my_exchange_name',
                      handlers=[process_color, process_address],
                      host='localhost')
xl.listen()


PUBLISHING:

xp = ExchangePublisher('my_exchange_name', host='localhost')

message = {'name': 'steve', 'favorite_color': 'green'}
xp.publish('process_color', message)

message = {'name': 'charlie', 'address': 'the moon'}
xp.publish('process_address', message)
'''

class ExchangeListener(Exchange):
    """A class for listening to an amqp exchange
    """

    def __init__(self, exchange, handlers=[], exchage_type='direct',
                 passive=False, durable=False, auto_delete=False,
                 internal=False, nowait=False, arguments=None, host='localhost',
                 port=None, virtual_host=None, credeitnals=None,
                 channel_max=None, frame_max=None, heartbeat_interval=None,
                 ssl=None, ssl_options=None, connection_attempts=None,
                 retry_delay=None, socket_timeout=None, locale=None,
                 backpressure_detection=None):
        """Construct an :class:`.ExchangeListener`.
        :param exchange: the name of the amqp exchange
        :param handlers: a list of listening handler functions. Each handler
        function should expect to be called with a single message that will be
        set to an instance of :class:`mq.message.Message`. Give each listening
        function the name of the routing key it should listen to.
        """
        self.exchange_config = dict(exchange_type=exchage_type, passive=passive,
                                    durable=durable, auto_delete=auto_delete,
                                    internal=internal, nowait=nowait,
                                    arguments=arguments, connection_params=dict(
                host=host, port=port, virtual_host=virtual_host,
                credentials=credeitnals, channel_max=channel_max,
                frame_max=frame_max, heartbeat_interval=heartbeat_interval,
                ssl=ssl, ssl_options=ssl_options,
                connection_attempts=connection_attempts,
                retry_delay=retry_delay, socket_timeout=socket_timeout,
                locale=locale, backpressure_detection=backpressure_detection),
                                    exchange=exchange)
        self.handler_config = {}
        self.handler_namespace = type('handler_namespace', (object,), {})
        self.exchange_config['connection_params'].update({'host': host})
        for handler in handlers:
            self.register_handler(handler)

    def register_handler(self, handler, routing_key=None, redeliver_attempts=5,
                         redeliver_delay=1, passive=False, durable=True,
                         exclusive=False, auto_delete=False, nowait=False,
                         x_ha_policy='all', x_ha_sync_mode='automatic'):
        """Registers the `handler` function to listen at the specified
        routing_key. If routing_key is not supplied, use the name of the
        function as the routing key.
        """
        routing_key = handler.__name__ if routing_key is None else routing_key
        assert(self.handler_config.get(routing_key) is None)
        self.handler_config[routing_key] = dict(handler_name=routing_key,
            redeliver_attempts=redeliver_attempts,
            redeliver_delay=redeliver_delay,
            passive=passive,
            durable=durable,
            exclusive=exclusive,
            auto_delete=auto_delete,
            nowait=nowait,
            arguments={
                "x-ha-policy": x_ha_policy,
                "x-ha-sync-mode": x_ha_sync_mode
            })
        handler_klass = type(routing_key, (MessageHandler,),
                             {'handle': lambda _self, msg: handler(msg)})
        setattr(self.handler_namespace, routing_key, handler_klass)

    def listen(self):
        super(ExchangeListener, self).__init__(self.handler_config,
                                               self.exchange_config,
                                               self.handler_namespace)
        super(ExchangeListener, self).run()

class ExchangePublisher(object):
    """A class for publishing to an AMQP exchange"""

    def __init__(self, exchange, host='localhost', port=None,
                 virtual_host=None, credentials=None, channel_max=None,
                 frame_max=None, heartbeat_interval=None, ssl=None,
                 ssl_options=None, connection_attempts=None,
                 retry_delay=None, socket_timeout=None, locale=None,
                 backpressure_detection=None):
        self._connection_config = {'connection_params': dict(host=host,
                               port=port,
                               virtual_host=virtual_host,
                               credentials=credentials,
                               channel_max=channel_max,
                               frame_max=frame_max,
                               heartbeat_interval=heartbeat_interval,
                               ssl=ssl,
                               ssl_options=ssl_options,
                               connection_attempts=connection_attempts,
                               retry_delay=retry_delay,
                               socket_timeout=socket_timeout,
                               locale=locale,
                               backpressure_detection=backpressure_detection)}
        self._exchange = exchange
        self._publishers = {}

    def _make_publisher(self, routing_key):
        publisher_config = {'exchanges': [self._exchange],
                            'routing_keys': [routing_key]}
        return Publisher(self._connection_config, publisher_config)

    def publish(self, routing_key, message):
        """Publish a message to the specified routing_key
        :param routing_key: a string representing the routing key to publish to
        :param message: a serializable key / value dictionary to pass
        """
        try:
            publisher = self._publishers[routing_key]
        except KeyError:
            publisher = self._make_publisher(routing_key)
            self._publishers[routing_key] = publisher
        publisher.publish(message)
