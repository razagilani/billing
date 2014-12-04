import json

from billing.core.model import Session
from billing.core.altitude import AltitudeUtility, get_utility_from_guid
from billing.exc import AltitudeDuplicateError


def consume_utility_guid(channel, queue_name, utilbill_processor):
    '''Register callback for AMQP messages to receive a utility.
    '''
    def callback(ch, method, properties, body):
        d = json.loads(body)
        name, guid = d['name'], d['utility_provider_guid']

        # TODO: this may not be necessary because unique constraint in the
        # database can take care of preventing duplicates
        s = Session()
        if s.query(AltitudeUtility).filter_by(guid=guid).count() != 0:
            raise AltitudeDuplicateError(
                'Altitude utility "%" already exists with name "%s"' % (
                    guid, name))

        new_utility = utilbill_processor.create_utility(name)
        s.add(AltitudeUtility(new_utility, guid))
        s.commit()
    channel.basic_consume(callback, queue=queue_name)

# TODO rename
def run(channel, queue_name, utilbill_processor):
    '''Register callback for AMQP messages to receive a utility bill.
    '''
    def callback(ch, method, properties, body):
        d = json.loads(body)
        utility = get_utility_from_guid(d['utility_guid'])
        utilbill_processor.upload_utility_bill_existing_file(
            d['account'], utility, d['sha256_hexdigest'])
        ch.basic_ack(delivery_tag=method.delivery_tag)
    channel.basic_consume(callback, queue=queue_name)

