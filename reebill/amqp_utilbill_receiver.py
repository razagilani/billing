



from billing import init_config, init_model, init_logging, config
from os.path import dirname, realpath, join
p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(path=p)
init_config(filename=p)
init_model()

from billing.lib.amqp import ExchangeListener
from billing.processing.state import Customer, UtilBill, Session, Utility, \
    Address

def upload_utility_bill(message):
    """Message is a dictionary with keys:
        utility_id -- id of the utility company
        account -- customer account number at the utility company
        sha256_hexdigest -- sha256 of the billpdf
        service_address
    """
    s = Session()
    customer = s.query(Customer).join(Utility).\
        filter(Customer.account == message['account']).\
        filter(Customer.fb_utility_id == message['utility_id']).one()
    utility = s.query(Utility).filter_by(id=message['utility_id']).one()
    sa = message['service_address']
    ub = UtilBill(customer, 0, '', utility, '', Address(),
                  Address(sa['addressee'], sa['street'], sa['city'],
                          sa['state'], sa['postal_code']),
                  sha256_hexdigest=message['sha256_hexdigest'])
    s.add(ub)
    s.commit()

xl = ExchangeListener(config.get('amqp', 'exchange'),
                      handlers=[upload_utility_bill])
xl.listen()
