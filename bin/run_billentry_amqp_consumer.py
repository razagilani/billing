import logging
from traceback import format_exc
from billentry.billentry_exchange import LOG_NAME, create_amqp_conn_params,\
    consume_utilbill_guids_mq

from core import initialize

if __name__ == '__main__':
    initialize()

    logger = logging.getLogger(LOG_NAME)
    logger.info('Starting run_billenty_ampq_consumers')

    try:
        exchange_name, routing_key, amqp_connection_parameters \
            = create_amqp_conn_params()
        consume_utilbill_guids_mq(exchange_name, routing_key,
                                 amqp_connection_parameters)
    except Exception as e:
        logger.critical('Exception in run_amqp_consumers:', exc_info=True)
        raise
    else:
        logger.warning('End of run_ampq_consumers: should never be reached!')


