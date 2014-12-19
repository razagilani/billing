#!/usr/bin/env/python
'''Entry point for AMQP consumers: run this file to start consuming messages.
This file should be kept as short as possible; all substantive code should go
in amqp_exchange.py (and should have test coverage).
'''
from billing import init_config, init_model, init_logging
from billing.core.amqp_exchange import create_dependencies, \
    consume_utility_guid, consume_utilbill_file

if __name__ == '__main__':
    init_config()
    init_model()
    init_logging()

    _, channel, _, queue_name, utilbill_processor = create_dependencies()

    consume_utilbill_file(channel, queue_name, utilbill_processor)

    # TODO: 'consume_utility_guid' is disabled because it was decided
    # that this should not be done after all (for now)
    #consume_utility_guid(channel, queue_name, utilbill_processor)
