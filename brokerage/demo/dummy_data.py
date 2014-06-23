from datetime import datetime as dt
from datetime import timedelta as td
from data.model import RateClass, Address
from data.model.brokerage import TimeRangeQuote, TimeRangeEstimator, \
    CommitmentPeriodEstimator
from data.model.company import Utility, Supplier
from data.model.orm import Session


def create_distributors_and_suppliers(session):
    """Define Distributors and Suppliers"""
    gas_distributors = [Utility(name='Washington Gas Distribution',
                                address=Address("Washington Gas Distribution",
                                               "123 Some Street", "Washington", "DC", "13093"),
                                rate_classes=['C1', 'GS1', 'GS2']),
                        Utility(name='BG&E',
                                address=Address("Colonial Energy Mail Room",
                                                "Great Street", "Fredericksburg", "VA", "22401"),
                                rate_classes=["R1", "C1", "C2"])]

    gas_suppliers = [Supplier(name='Hess',
                                 address=Address("Hess Small Business",
                                                 "1 Hess Plaza", "Woodbridge", "NJ", "07095")),
                     Supplier(name='Washington Gas Supply',
                                 address=Address("Hess Small Business",
                                                 "1 Hess Plaza", "Woodbridge", "NJ", "07095")),
                     Supplier(name="Constillation",
                              address=Address("Constillation Mailroom",
                                              "1 Hess Plaza", "Woodbridge", "NJ", "07095")),
                     Supplier(name="Direct Energy",
                              address=Address("Direct Energy",
                                              "1 Some Street", "Annapolis", "MD", "19930"))]

    session.add_all(gas_distributors + gas_suppliers)
    session.flush()


def create_supplier_quotes(session):
    """Define supplier quotes"""
    wgas = session.query(Supplier).filter_by(name='Washington Gas Supply').one()

    hess = session.query()
    hess_c1 = hess.rate_classes.filter_by(name='C1')
    hess_gs1 = hess.rate_classes.filter_by(name='GS1')

    #TimeRangeQuotes
    for supplier, rate_class, quote, sos, start_time, end_time, time_issued in\
        [(wgas, hess_c1, 0.75, True, dt(2014, 6, 1), dt(2014, 9, 1), dt(2014, 5, 1)),
         (wgas, hess_c1, 0.8, True, dt(2014, 9, 1), dt(2015, 1, 1), dt(2014, 5, 1)),
         (wgas, hess_gs1, 0.9, True, dt(2014, 6, 1), dt(2014, 9, 1), dt(2014, 5, 1))]:
        session.add(TimeRangeQuote(supplier, rate_class, quote, sos, start_time,
                                     end_time, time_issued))
    for


def create_estimators(session):
    session.add_all([TimeRangeEstimator(session),
                     CommitmentPeriodEstimator(session)])

"""
Proof of concept
"""

session = Session()

create_distributors_and_suppliers(session)
create_supplier_quotes(session)
create_estimators(session)

offers = [e.estimate_offers for e in ]


gse.estimate_offers




