#!/usr/bin/env/python
'''Entry point for AMQP consumers: run this file to start consuming messages.
This file should be kept as short as possible; all substantive code should go
in amqp_exchange.py (and should have test coverage).
'''
import logging
from traceback import format_exc

from core import init_config, init_model, init_logging
from core.amqp_exchange import create_dependencies, \
    consume_utilbill_file_mq, LOG_NAME

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()

    logger = logging.getLogger(LOG_NAME)
    logger.info('Starting run_ampq_consumers')

    try:
        exchange_name, routing_key, amqp_connection_parameters, \
            utilbill_processor = create_dependencies()
        consume_utilbill_file_mq(exchange_name, routing_key,
                                 amqp_connection_parameters, utilbill_processor)
    except Exception as e:
        logger.critical('Exception in run_amqp_consumers:', exc_info=True)
        raise
    else:
        logger.warning('End of run_ampq_consumers: should never be reached!')


