import json
from formencode.validators import String, Regex, FancyValidator, OneOf, \
    ConfirmType
from formencode import Schema
from formencode import Invalid
from formencode.foreach import ForEach
import re

from billing.core.bill_file_handler import BillFileHandler
from billing.core.model import Session, Address, UtilityAccount
from billing.core.altitude import AltitudeUtility, get_utility_from_guid, \
    AltitudeGUID, update_altitude_account_guids
from billing.exc import AltitudeDuplicateError

class ExactValue(FancyValidator):
    '''Validator that checks for a specific value, and also supports lists.
    It's hard to believe Formencode doesn't have this built in, but I couldn't
    find it.
    '''
    def __init__(self, value):
        super(ExactValue, self).__init__(accept_iterator=True)
        self._value = value
    def _validate_python(self, value, state):
        if value != self._value:
            raise Invalid('Expected %s, got %s' % (self._value, value),
                          value, state)
        return value

class TotalValidator(FancyValidator):
    '''Validator for the "total" field in utility bill messages: dollars and
    cents as a string preceded by "$" (limited to 2 decimal places), or empty.
    '''
    def _convert_to_python(self, value, state):
        if not isinstance(value, basestring):
            raise Invalid('Expected string: %s' % value, value, state)
        substr = re.match('(^\$\d*\.?\d{1,2}$)|^$', value)
        if substr is None:
            raise Invalid('Invalid "total" string: "%s"' % value, value, state)
        return None if substr == '' else float(substr.group(0)[1:])

class UtilbillMessageSchema(Schema):
    '''Formencode schema for validating/parsing utility bill message contents.
    specification is at
    https://docs.google.com/a/nextility.com/document/d
    /1u_YBupWZlpVr_vIyJfTeC2IaGU2mYZl9NoRwjF0MQ6c/edit
    '''
    message_version = ExactValue([1,0])
    utility_account_number = ConfirmType(subclass=basestring)
    utility_provider_guid = Regex(regex=AltitudeGUID.REGEX)
    sha256_hexdigest = Regex(regex=BillFileHandler.HASH_DIGEST_REGEX)
    #due_date = String()
    total = TotalValidator()
    service_address = ConfirmType(subclass=basestring)
    account_guids = ForEach(Regex(regex=AltitudeGUID.REGEX))

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
    def callback(ch, method, properties, body):
        s = Session()
        d = UtilbillMessageSchema.to_python(json.loads(body))
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

