import json
from formencode.validators import String, Regex, FancyValidator
from formencode import Schema
from formencode.api import Invalid
from formencode.foreach import ForEach
import re

from billing.core.bill_file_handler import BillFileHandler
from billing.core.model import Session, Address, UtilityAccount
from billing.core.altitude import AltitudeUtility, get_utility_from_guid, \
    AltitudeGUID, update_altitude_account_guids
from billing.exc import AltitudeDuplicateError

class TotalValidator(FancyValidator):
    '''Validator for the odd format of the "total" field in utility bill
    messages: dollars and cents as a string preceded by "$", or empty.
    '''
    def _convert_to_python(self, value, state):
        substr = re.match('^\$\d*\.?\d{1,2}|$', value).group(0)
        if substr is None:
            raise Invalid('Invalid "total" string: "%s"' % value, value, state)
        return None if substr == '' else float(substr[1:])

class UtilbillMessageSchema(Schema):
    '''Formencode schema for validating/parsing utility bill message contents.
    specification is at
    https://docs.google.com/a/nextility.com/document/d
    /1u_YBupWZlpVr_vIyJfTeC2IaGU2mYZl9NoRwjF0MQ6c/edit
   '''
    utility_account_number = String()
    utility_provider_guid = Regex(regex=AltitudeGUID.REGEX)
    sha256_hexdigest = Regex(regex=BillFileHandler.HASH_DIGEST_REGEX)
    #due_date = String()
    total = TotalValidator()
    service_address = String()
    account_guids = ForEach(Regex(regex=AltitudeGUID.REGEX))


# TODO: this code is not used yet (and not tested). it was originally decided
#  that it was necessary to synchronize utilities between altitude and
# billing databases, but this was later un-decided, so nothing is being done
# about it for now. see BILL-3784.
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
    def callback(ch, method, properties, body):
        d = UtilbillMessageSchema.to_python(json.loads(body))
        s = Session()
        utility = get_utility_from_guid(d['utility_provider_guid'])
        utility_account = s.query(UtilityAccount).filter_by(
            account_number=d['utility_account_number']).one()
        sha256_hexdigest = d['sha256_hexdigest']
        total = d['total']
        # TODO due_date
        service_address_street = d['service_address']
        account_guids = d['account_guids']

        utilbill_processor.create_utility_bill_with_existing_file(
            utility_account, utility, sha256_hexdigest,
            target_total=total,
            service_address=Address(street=service_address_street))
        update_altitude_account_guids(utility_account, account_guids)
        s.commit()
        ch.basic_ack(delivery_tag=method.delivery_tag)
    channel.basic_consume(callback, queue=queue_name)

