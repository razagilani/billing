import json
from formencode.validators import String
from formencode import Schema

from billing.core.model import Session, Address
from billing.core.altitude import AltitudeUtility, get_utility_from_guid
from billing.exc import AltitudeDuplicateError


class UtilbillMessageSchema(Schema):
    # TODO add more criteria than just type for validity
    account = String()
    sha256_hexdigest = String()
    due_date = String()
    # total = String()
    service_address = String()


# TODO: this is not used yet and not tested (BILL-3784); it's serving to show
# how the AltitudeUtility table (BILL-5836) will be used.
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

def consume_utilbill_file(channel, queue_name, utilbill_processor):
    '''Register callback for AMQP messages to receive a utility bill.
    '''
    def parse_total(total_str):
        assert isinstance(total_str, basestring) and (total_str == '' or
               total_str[0] == '$')
        if total_str == '':
            return None
        return float(total_str[1:])

    def callback(ch, method, properties, body):
        # TODO use validation
        d = json.loads(body)
        utility = get_utility_from_guid(d['utility_guid'])
        account = d['account']
        sha256_hexdigest = d['sha256_hexdigest']
        total = parse_total(d['total'])
        # TODO due_date
        service_address_street = d['service_address']

        utilbill_processor.create_utility_bill_with_existing_file(
            account, utility, sha256_hexdigest,
            target_total=total, service_address=Address(
                street=service_address_street))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    channel.basic_consume(callback, queue=queue_name)

