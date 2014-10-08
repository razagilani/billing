from billing import init_config, init_model, init_logging
from os.path import dirname, realpath, join
p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(filepath=p)
init_config(filepath=p)
init_model()

from billing import config

from sqlalchemy.sql.expression import desc
from billing.mq.simple import SimpleExchange
from billing.core.model import Customer, UtilBill, Session, Utility, \
    Address


def process_utility_bill(utility_provider_guid, account_number,
                        sha256_hexdigest):
    """
    :param utility_provider_guid: the GUID of the utility company
    :param account_number: the account number at the utility company
    :param sha256_hexdigest: the hexdigest of the utilbill PDF
    """
    s = Session()

    utility = s.query(Utility).filter_by(guid=utility_provider_guid).one()

    customer = s.query(Customer).filter_by(account=account_number).first()
    customer = customer if customer else Customer('', account_number, 0, 0, '',
        utility, '', Address(), Address())

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

def process_utility(name, utility_provider_guid):
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
    xl = SimpleExchange(config.get('amqp', 'exchange'),
                        handlers=[process_utility_bill,
                                  process_utility])
    xl.listen()

if __name__ == '__main__':
    run_exchange()