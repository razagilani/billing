#!/usr/bin/env/python
'''Entry point for AMQP consumers: run this file to start consuming messages.
This file should be kept as short as possible; all substantive code should go
in amqp_exchange.py (and should have test coverage).
'''
from billing import init_config, init_model, init_logging
from billing.core.amqp_exchange import create_dependencies, \
    ConsumeUtilbillFileHandler
from billing.mq import MessageHandlerManager

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()

    exchange_name, routing_key, amqp_connection_parameters, \
        utilbill_processor = create_dependencies()

    def create_consume_utilbill_file_handler():
        return ConsumeUtilbillFileHandler(
            exchange_name, routing_key, amqp_connection_parameters,
            utilbill_processor)

    mgr = MessageHandlerManager(amqp_connection_parameters)
    mgr.attach_message_handler(
        exchange_name, routing_key, create_consume_utilbill_file_handler
    )
    mgr.run()
