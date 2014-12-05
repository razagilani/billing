import json
from billing.core.model import Session, Utility, \
    Address


# TODO: this is not used yet and is probably not working
def process_utility(name, utility_provider_guid):
    """Receives the utility from XBill over AMQP"""
    s = Session()
    utility = s.query(Utility).filter_by(guid=utility_provider_guid).first()
    if utility:
        utility.name = name
    else:
        utility = Utility(name=name,
                          address=Address(),
                          guid=utility_provider_guid)
        s.add(utility)
    s.commit()

def run(channel, queue_name, utilbill_processor):
    '''Wait for AMQP messages to receive a utility bill.
    '''
    def callback(ch, method, properties, body):
        d = json.loads(body)
        utilbill_processor.create_utility_bill_with_existing_file(
            d['account'], d['utility_guid'], d['sha256_hexdigest'])
        ch.basic_ack(delivery_tag=method.delivery_tag)
    channel.basic_consume(callback, queue=queue_name)

