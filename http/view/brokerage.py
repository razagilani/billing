from flask_mako import render_template, render_template_def
import logging
from billing.brokerage.demo.proof_of_concept import drop_create_tables, create_companies, \
    create_quotes, create_offer_makers, create_users, create_customer_interest
from billing.data.model import Session, CustomerInterest

log = logging.getLogger(__name__)


def quotes():
    return 'quotes'

def quote_view(quote_id):
    return 'quote_view: %s' % quote_id

def offer_view(offer_id):
    return 'offer_view: %s' % offer_id

def interest_edit(interest_id):
    return 'interest edit'

def interest_view(interest_id):
    return 'interest view'

def generate_offers(interest_id):
    return 'interest generate offers'

def customer_interest():
    s = Session()
    interests = s.query(CustomerInterest).all()
    return render_template('interest.mako', interests=interests)

def dummy_data():
    drop_create_tables()
    session = Session()
    create_companies(session)
    create_quotes(session)
    create_offer_makers(session)
    create_users(session)
    create_customer_interest(session)
    log.info('commiting database dummy data')
    session.commit()
    return 'done'