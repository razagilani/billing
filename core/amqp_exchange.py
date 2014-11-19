from billing import init_config, init_model, init_logging
from os.path import dirname, realpath, join
p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(filepath=p)
init_config(filepath=p)
init_model()

from billing import config

from sqlalchemy.sql.expression import desc
from billing.mq import Exchange, MessageHandler
from billing.mq.schemas.schemas import process_utility_bill_schema,\
    process_utility_schema
from billing.core.model import Customer, UtilBill, Session, Utility, \
    Address


class ProcessUtilityBillHander(MessageHandler):
    """Receives a utility bill over AMQP

    Message schema:
    See Integration Specifications in GDrive > Team Tech > Integration
    Specifications > Working > Billing > MQ Specification > process_utility_bill
    """

    message_schema = process_utility_bill_schema

    def handle(self, message):
        utility_provider_guid = message['utility_provider_guid']
        account_number = message['utility_account_number']
        sha256_hexdigest = message['sha256_hexdigest']

        s = Session()

        utility = s.query(Utility).filter_by(guid=utility_provider_guid).one()

        # TODO: use of 'account_number' argument does not match docstring
        # https://skylineinnovations.atlassian.net/browse/BILL-5757
        customer = s.query(Customer).filter_by(account=account_number).first()
        customer = customer if customer else Customer('', account_number, 0, 0, '',
            utility, '', Address(), Address())

        # TODO replace with UtilbillLoader.get_last_real_utilbill
        prev = s.query(UtilBill).filter_by(customer=customer).\
            filter_by(state=UtilBill.Complete).\
            order_by(desc(UtilBill.period_start)).first()

        ub = UtilBill(customer, UtilBill.Complete, getattr(prev, 'service', ''),
                      utility, getattr(prev, 'rate_class', ''),
                      Address.from_other(prev.billing_address) if \
                          prev else Address(),
                      Address.from_other(prev.service_address) if \
                          prev else Address(),
                      sha256_hexdigest=sha256_hexdigest)
        s.add(ub)
        s.commit()


class ProcessUtilityHandler(MessageHandler):
    """Receives a utility over AMQP

    Message schema:
    See Integration Specifications in GDrive > Team Tech > Integration
    Specifications > Working > Billing > MQ Specification > process_utility
    """

    message_schema = process_utility_schema

    def handle(self, message):
        name = message['name']
        utility_provider_guid = message['guid']

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


def run_exchange():
    e = Exchange(config.get('amqp', 'exchange'))
    e.attach_handler('process_utility_bill', ProcessUtilityBillHander)
    e.attach_handler('process_utility', ProcessUtilityHandler)
    e.run()

if __name__ == '__main__':
    run_exchange()