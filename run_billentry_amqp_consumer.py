import logging
from traceback import format_exc
from billentry.billentry_exchange import LOG_NAME, create_amqp_conn_params,\
    consume_utilbill_guids_mq

from core import init_config, init_model, init_logging

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()

    logger = logging.getLogger(LOG_NAME)
    logger.info('Starting run_ampq_consumers')

    try:
        exchange_name, routing_key, amqp_connection_parameters \
            = create_amqp_conn_params()
        print exchange_name
        print routing_key
        consume_utilbill_guids_mq(exchange_name, routing_key,
                                 amqp_connection_parameters)
    except Exception as e:
        logger.critical('Exception in run_amqp_consumers:', exc_info=True)
        raise
    else:
        logger.warning('End of run_ampq_consumers: should never be reached!')

