from flask_mako import render_template, render_template_def
import logging
from werkzeug.datastructures import MultiDict
from billing.brokerage.demo.proof_of_concept import drop_create_tables, create_companies, \
    create_quotes, create_offer_makers, create_users, create_customer_interest
from billing.data.model import Session, CustomerInterest, RateClass
from http.form import InterestEdit
from flask import request

log = logging.getLogger(__name__)


class Obj(object):
    def __init__(self, dct):
        self._dct = dct

    def __getattr__(self, item):
        return self._dct[item]


def quotes():
    return 'quotes'


def quote_view(quote_id):
    return 'quote_view: %s' % quote_id


def offer_view(offer_id):
    return 'offer_view: %s' % offer_id


def interest_edit(interest_id):
    s = Session()
    interest = s.query(CustomerInterest).filter_by(id=interest_id).one()

    form = InterestEdit(obj=Obj({'name': interest.customer.name,
                                 'street': interest.address.street,
                                 'city': interest.address.city,
                                 'state': interest.address.state,
                                 'postal_code': interest.address.postal_code,
                                 'rate_class': interest.rate_class.id,
                                 'use_periods': "\n".join(["%s, %s, %s" %
                                     (u.time_start.date(), u.time_end.date(),
                                     u.quantity) for u in interest.use_periods])
                                }))
    form.rate_class.choices = [(r.id, "%s - %s" % (r.utility.name, r.name))
                              for r in s.query(RateClass).all()]
    if form.validate_on_submit():
        flash('hello')
        print 'form validate on submit'
    return render_template('interest_edit.mako', interest=interest, form=form)


def interest_view(interest_id):
    s = Session()
    interest = s.query(CustomerInterest).filter_by(id=interest_id).one()
    return render_template('interest_view.mako', interest=interest)


def generate_offers(interest_id):
    s = Session()
    interest = s.query(CustomerInterest).filter_by(id=interest_id).one()

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