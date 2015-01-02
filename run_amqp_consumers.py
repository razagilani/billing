#!/usr/bin/env/python
'''Entry point for AMQP consumers: run this file to start consuming messages.
This file should be kept as short as possible; all substantive code should go
in amqp_exchange.py (and should have test coverage).
'''
from billing import init_config, init_model, init_logging
from billing.core.amqp_exchange import create_dependencies, \
    ConsumeUtilbillFileHandler, consume_utilbill_file_mq
from billing.mq import MessageHandlerManager

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()

    exchange_name, routing_key, amqp_connection_parameters, \
        utilbill_processor = create_dependencies()
    consume_utilbill_file_mq(exchange_name, routing_key,
                             amqp_connection_parameters, utilbill_processor)
