from datetime import datetime as dt
from datetime import timedelta as td
from brokerage.use_period import UsePeriod
from data.model import RateClass, Address
from data.model.brokerage import TimeBlockQuote, TimeRangeEstimator, \
    CommitmentPeriodEstimator, CommitmentPeriodQuote, Estimator
from data.model.company import Utility, Supplier
from data.model.orm import Session


def create_companies(session):
    """Create utilities and suppliers"""
    gas_utilities = [Utility(name='Washington Gas',
                        address=Address("Washington Gas Distribution",
                                       "123 Some Street", "Washington", "DC", "13093"),
                        rate_classes=['C1', 'GS1', 'GS2']),
                    Utility(name='Columbia Gas',
                        address=Address("Columbia Gas Mail Room",
                                        "Great Street", "Fredericksburg", "VA", "22401"),
                        rate_classes=["R1", "C1", "C2"])]

    gas_suppliers = [Supplier(name='Hess',
                         address=Address("Hess Small Business",
                                         "1 Hess Plaza", "Woodbridge", "NJ", "07095")),
                    Supplier(name="Constillation",
                      address=Address("Constillation Mailroom",
                                      "1 Hess Plaza", "Woodbridge", "NJ", "07095")),
                    Supplier(name="Direct Energy",
                      address=Address("Direct Energy",
                                      "1 Some Street", "Annapolis", "MD", "19930"))]

    elec_utilities = [Utility(name='Pepco',
                        address=Address("Charlie",
                                       "123 Some Street", "Washington", "DC", "13093"),
                        rate_classes=['R', 'RAD', 'RTM']),
                      Utility(name='Delmarva',
                        address=Address("Delmarva Mail Room",
                                        "Great Street", "Fredericksburg", "VA", "22401"),
                        rate_classes=["R", "RAD", "RTM"])]

    elec_suppliers = [Supplier(name='Think Energy',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093")),
                      Supplier(name='Hudson Energy',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093")),
                      Supplier(name='Liberty Power',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093"))]

    session.add_all(gas_utilities + gas_suppliers + elec_utilities + elec_suppliers)
    session.flush()


def create_quotes(session):
    """Define supplier quotes"""
    sq = lambda s: session.query(Supplier).filter_by(name=s).one()
    uq = lambda u: session.query(Utility).filter_by(name=u).one()
    rc = lambda(sup, s): sup.rate_classes.filter_by(name=s).one()

    #gas suppliers
    hess = sq('Hess Small Business')
    constil = sq('Constillation')
    direct = sq('Direct Energy')

    #elec suppliers
    think = sq('Think Energy')
    hudson = sq('Hudson Energy')
    liberty = sq('Libarty Power')

    #gas utilities
    wgas = uq('Washington Gas')
    bge = uq('BG&E')

    #elec utilities
    pepco = uq('Pepco')
    delmarva = uq('Delmarva')

    #TimeRangeQuotes (SOS quotes)
    for supplier, rate_class, quote, block_min, block_max, charge, time_issued, start_time, end_time in\
        [#Washington Gas SOS Supply C1 Jun 1, 2014 - Sept 1, 2014
         (wgas, rc(wgas, 'C1'), 0.75, 0, 350, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (wgas, rc(wgas, 'C1'), 0.70, 350, 700, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (wgas, rc(wgas, 'C1'), 0.60, 700, None, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Washington Gas SOS Supply C1 Sept 1, 2014 - Dec 1, 2014
         (wgas, rc(wgas, 'C1'), 0.90, 0, 350, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),
         (wgas, rc(wgas, 'C1'), 0.80, 350, 700, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),
         (wgas, rc(wgas, 'C1'), 0.70, 700, None, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),


         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.125, 0, 350, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.11, 350, 700, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.10, 700, None, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.13, 0, 350, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.125, 350, 700, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.11, 700, None, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.006, 0, 350, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.005, 350, 700, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.004, 700, None, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.006, 0, 350, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.0055, 350, 700, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.005, 700, None, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),


          #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.135, 0, 350, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.13, 350, 700, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.12, 700, None, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.14, 0, 350, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.135, 350, 700, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.12, 700, None, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.007, 0, 350, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.0065, 350, 700, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.005, 700, None, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.007, 0, 350, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.0065, 350, 700, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.006, 700, None, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1))]:

        session.add(TimeBlockQuote(start_time, end_time, block_min, block_max, supplier, rate_class, quote, charge, time_issued))

    #CommitmentPeriodQuotes (non-SOS quotes)
    for (commitment_months, supplier, rate_class, quote, charge, time_isued) in \
        [#Think energy supply for Pepco
         (6, think, rc(pepco('RAD')), 0.10, 'generation', dt(2014, 5, 1)),
         (6, think, rc(pepco('RAD')), 0.007, 'transmission', dt(2014, 5, 1)),
         (12, think, rc(pepco('RAD')), 0.95, 'generation', dt(2014, 5, 1)),
         (12, think, rc(pepco('RAD')), 0.0065, 'transmission', dt(2014, 5, 1)),

         #Hudson energy supply for Pepco
         (6, hudson, rc(pepco('RAD')), 0.07, 'generation', dt(2014, 5, 1)),
         (6, hudson, rc(pepco('RAD')), 0.007, 'transmission', dt(2014, 5, 1)),
         (12, hudson, rc(pepco('RAD')), 0.13, 'generation', dt(2014, 5, 1)),
         (12, hudson, rc(pepco('RAD')), 0.007, 'transmission', dt(2014, 5, 1))]:

        session.add(CommitmentPeriodQuote(commitment_months, supplier, rate_class,
            quote, charge, time_issued))
    session.flush()


def create_estimators(session):
    session.add_all([TimeRangeEstimator(session),
                     CommitmentPeriodEstimator(session)])
    session.flush()

def drop_create_tables():
    pass


"""
Proof of concept
"""

session = Session()

create_companies(session)
create_quotes(session)
create_estimators(session)


rate_class = session.query(RateClass).join(Utility).\
    filter(Utility.name == 'Pepco').filter(RateClass.name == 'RAD').\
    filter(RateClass.active == True).one()

use_periods = [UsePeriod(650, dt(2013, 9, 1), dt(2013, 10, 1)),
               UsePeriod(700, dt(2013, 10, 1), dt(2013, 11, 1)),
               UsePeriod(710, dt(2013, 11, 1), dt(2013, 12, 1)),
               UsePeriod(580, dt(2013, 12, 1), dt(2014, 1, 1)),
               UsePeriod(600, dt(2014, 1, 1), dt(2014, 2, 1)),
               UsePeriod(620, dt(2014, 2, 1), dt(2014, 3, 1)),
               UsePeriod(800, dt(2014, 3, 1), dt(2014, 4, 1))]

offers = []
for estimator in session.query(Estimator).filter_by(active=True).all():
    offers.extend(estimator.estimate_offers(rate_class, use_periods))


for offer in offers:
    print offer







