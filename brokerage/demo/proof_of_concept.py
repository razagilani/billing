from datetime import datetime, timedelta
from datetime import timedelta as td
#from brokerage.use_period import UsePeriod
from billing.data.model import RateClass, Address, Base, Session, Supplier, Utility, \
    BlockQuote, BlockOfferMaker, TermOfferMaker, OfferMaker, TermQuote, UsePeriod, Company
from itertools import product
from hashlib import sha256

import logging

log = logging.getLogger(__name__)


def tuplize(ls):
    """[1, 2, 3, 4, 5] --> [(1, 2), (2, 3), (3, 4), (4, 5)]"""
    r = []
    for i in range(len(ls) - 1):
        r.append((ls[i], ls[i + 1]))
    return r


def drop_create_tables():
    log.debug('Dropping all tables')
    Base.metadata.drop_all(checkfirst=True)
    log.debug('Creating all tables')
    Base.metadata.create_all()


def create_companies(session):

    log.info("Creating companies")
    """Create utilities and suppliers"""
    gas_utilities = [Utility(name='Washington Gas',
                        address=Address("Washington Gas Distribution",
                                       "123 Some Street", "Washington", "DC", "13093"),
                        service='gas',
                        rate_classes=['C1', 'GS1', 'GS2']),
                    Utility(name='Columbia Gas',
                        address=Address("Columbia Gas Mail Room",
                                        "Great Street", "Fredericksburg", "VA", "22401"),
                        service='gas',
                        rate_classes=["R1", "C1", "C2"])]

    gas_suppliers = [Supplier(name='Hess',
                         address=Address("Hess Small Business",
                                         "1 Hess Plaza", "Woodbridge", "NJ", "07095"),
                         service='gas'),
                    Supplier(name="Constillation",
                      address=Address("Constillation Mailroom",
                                      "1 Hess Plaza", "Woodbridge", "NJ", "07095"),
                      service='gas'),
                    Supplier(name="Direct Energy",
                      address=Address("Direct Energy",
                                      "1 Some Street", "Annapolis", "MD", "19930"),
                        service='gas')]

    elec_utilities = [Utility(name='Pepco',
                        address=Address("Charlie",
                                       "123 Some Street", "Washington", "DC", "13093"),
                        service='electric',
                        rate_classes=['R', 'RAD', 'RTM']),
                      Utility(name='Delmarva',
                        address=Address("Delmarva Mail Room",
                                        "Great Street", "Fredericksburg", "VA", "22401"),
                          service='electric',
                        rate_classes=["R", "RAD", "RTM"])]

    elec_suppliers = [Supplier(name='Think Energy',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093"),
                            service='electric'),
                      Supplier(name='Hudson Energy',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093"),
                            service='electric'),
                      Supplier(name='Liberty Power',
                          address=Address("TE", "123 Some Street", "Washington", "DC", "13093"),
                            service='electric')]

    session.add_all(gas_utilities + gas_suppliers + elec_utilities + elec_suppliers)
    session.flush()


def create_block_quote(utility, start, end, block_min, block_max, rate_class, charge, time_expired):
    """Determinstically makes a block quote"""

    assert(utility.service in ['electric', 'gas'])

    block_factor = 40
    if utility.service == 'electric':
        block_factor = 200

    rcord = ord(rate_class.name[-1])

    escalator = 1 + int(block_min / block_factor) * 0.02
    base = 1.0 if (len(utility.name) + rcord + time_expired.day if \
                        time_expired else 0) % 2 == 0 else 0.90

    offset = int(block_min / (block_factor * 1.5)) * 0.05

    if start.month % 2 == 0:
        offset = offset + 0.05

    rate = base - offset
    if utility.service == 'electric':
        if charge == 'generation':
            rate = round(rate / 5.0, 3)
        elif charge == 'transmission':
            rate = round(rate / 20.0, 3)

    time_issued = start - timedelta(days=rcord)
    return BlockQuote(start, end, block_min, block_max, escalator, utility,
                        rate_class, rate, charge, time_issued, 'xxref',
                        time_expired)


def create_block_quotes(session, utilities, blocks, dates, expiration_times, charges):
    for utility, (start, end), (block_min, block_max), expiration_time, \
        charge in product(utilities, dates, blocks, expiration_times, charges):
        for rate_class in utility.rate_classes:
            block_quote = create_block_quote(utility, start, end, block_min,
                block_max, rate_class, charge, expiration_time)
            session.add(block_quote)


def create_term_quote(supplier, term_months, rate_class, time_issued, time_expired, charge,
                      annual_min, annual_max, service_start_begin,
                      service_start_end):
    """Determinstically creates a term quote"""
    assert(supplier.service in ['electric', 'gas'])
    if supplier.service == 'electric':
        factor, rng = 0.1, 0.05
        annual_reduce = [0, 75, 150, 250, 500, 2000]
    else:
        factor, rng = 0.75, 0.2  # gas
        annual_reduce = [0, 600, 1200, 2500, 5000]
    x = annual_reduce.index(next(i for i in annual_reduce if i <= annual_min))
    rduce = 1 - float(x) / (4 * len(annual_reduce))
    sha = sha256("".join([str(x) for x in supplier.id, term_months, rate_class,
                                  time_expired, charge]))
    x = 8 - int(sha.hexdigest()[-1], 16)  # x is an integer between [-7, 8]
    rate = rduce * (factor + rng * (x / 8.0))

    return TermQuote(term_months, annual_min, annual_max, service_start_begin,
                     service_start_end, supplier, rate_class, rate, charge,
                     time_issued, 'xxref')


def create_term_quotes(session, suppliers, utilities, term_months_lst,
                       times_issued_expired, annual_volumes, service_start_ranges,
                       charges):
    for supplier, utility, term_months, (time_issued, time_expired), charge, \
        (annual_min, annual_max), (service_start_begin, service_start_end) in \
            product(suppliers, utilities, term_months_lst, times_issued_expired,
                    charges, annual_volumes, service_start_ranges):
        for rate_class in utility.rate_classes:
            term_quote = create_term_quote(supplier, term_months,
                rate_class, time_issued, time_expired, charge, annual_min,
                annual_max, service_start_begin, service_start_end)
            session.add(term_quote)


def print_quotes(session):

    #Block Quotes
    column_names = [s for s in BlockQuote.column_names() if s not in
                   ['discriminator', 'id', 'rate_class_id', 'company_id']]
    print "\n\nFound %s block quotes" % session.query(BlockQuote).count()
    print ", ".join(['company', 'rate_class'] + column_names)
    for block_quote in session.query(BlockQuote):
        print ", ".join([block_quote.company.name,
                         block_quote.rate_class.name] +
                        [str(getattr(block_quote, n)) for n in column_names])

    #Term Quotes
    column_names = [s for s in TermQuote.column_names() if s not in
                   ['discriminator', 'id', 'rate_class_id', 'company_id']]
    print "\n\nFound %s term quotes" % session.query(TermQuote).count()
    print ", ".join(['supplier', 'utility', 'rate_class'] + column_names)
    for term_quote in session.query(TermQuote):
        print ", ".join([term_quote.company.name,
                         term_quote.rate_class.utility.name,
                         term_quote.rate_class.name] +
                        [str(getattr(term_quote, n)) for n in column_names])

def create_quotes(session):
    log.debug("Creating Gas Block quotes")

    dates = tuplize([datetime(2013, 1, 1), datetime(2013, 4, 1),
                     datetime(2013, 7, 1), datetime(2013, 10, 1),
                     datetime(2014, 1, 1), datetime(2014, 4, 1),
                     datetime(2014, 7, 1), datetime(2014, 10, 1)])

    term_months = [6, 12, 24]

    gas_utilities = session.query(Utility).filter_by(service='gas').all()
    gas_suppliers = session.query(Supplier).filter_by(service='gas').all()
    gas_annual_volumes = [(0, None)]
    gas_blocks = [(0, None)]
    gas_expiration_times = [datetime(2013, 12, 15), None]

    elec_utilities = session.query(Utility).filter_by(service='electric').all()
    elec_suppliers = session.query(Supplier).filter_by(service='electric').all()
    elec_annual_volumes = tuplize([0, 75, 150, 250, 500, 2000])
    elec_blocks = tuplize([0, 350, 800, None])
    elec_expiration_times = [datetime(2013, 11, 10), None]

    #All Block Quotes
    create_block_quotes(session, gas_utilities, gas_blocks, dates,
        gas_expiration_times, ['supply'])
    create_block_quotes(session, elec_utilities, elec_blocks, dates,
        elec_expiration_times, ['generation', 'transmission'])

    #All Term Quotes
    times_issued_expired = [(datetime(2014, 6, 27, 11, 00), datetime(2014, 6, 27, 16, 00)),
                            (datetime(2014, 6, 26, 11, 00), datetime(2014, 6, 26, 16, 00))]
    service_start_ranges = [(datetime(2014, 7, 1), datetime(2014, 8, 1)),
                            (datetime(2014, 8, 1), datetime(2014, 9, 1))]
    create_term_quotes(session, elec_suppliers, elec_utilities, term_months,
        times_issued_expired, elec_annual_volumes, service_start_ranges,
        ['generation'])
    create_term_quotes(session, gas_suppliers, gas_utilities, term_months,
        times_issued_expired, gas_annual_volumes, service_start_ranges,
        ['supply'])



'''
def create_quotes(session):
    log.debug('Creating quotes')
    create_block_quotes(session)
    return

    """Define supplier quotes"""
    sq = lambda s: session.query(Supplier).filter_by(name=s).one()
    uq = lambda u: session.query(Utility).filter_by(name=u).one()
    rc = lambda sup, s: sup.rate_classes.filter_by(name=s).one()

    #gas suppliers
    hess = sq('Hess')
    constil = sq('Constillation')
    direct = sq('Direct Energy')

    #elec suppliers
    think = sq('Think Energy')
    hudson = sq('Hudson Energy')
    liberty = sq('Liberty Power')

    #gas utilities
    wgas = uq('Washington Gas')
    columbia = uq('Columbia Gas')

    #elec utilities
    pepco = uq('Pepco')
    delmarva = uq('Delmarva')

    #TimeRangeQuotes (SOS quotes)
    for company, rate_class, quote, block_min, block_max, escalator, charge, time_issued, start_time, end_time in\
        [#Washington Gas SOS Supply C1 Jun 1, 2014 - Sept 1, 2014
         (wgas, rc(wgas, 'C1'), 0.75, 0, 350, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (wgas, rc(wgas, 'C1'), 0.70, 350, 700, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (wgas, rc(wgas, 'C1'), 0.60, 700, None, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Washington Gas SOS Supply C1 Sept 1, 2014 - Dec 1, 2014
         (wgas, rc(wgas, 'C1'), 0.90, 0, 350, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),
         (wgas, rc(wgas, 'C1'), 0.80, 350, 700, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),
         (wgas, rc(wgas, 'C1'), 0.70, 700, None, 1.01, 'supply', dt(2014, 5, 1), dt(2014, 9, 1), dt(2014, 12, 1)),


         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.125, 0, 350, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.11, 350, 700, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.10, 700, None, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.13, 0, 350, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.125, 350, 700, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.11, 700, None, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.006, 0, 350, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.005, 350, 700, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'RAD'), 0.004, 700, None, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation RAD Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'RAD'), 0.006, 0, 350, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.0055, 350, 700, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'RAD'), 0.005, 700, None, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),


          #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.135, 0, 350, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.13, 350, 700, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.12, 700, None, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.14, 0, 350, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.135, 350, 700, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.12, 700, None, 1.01, 'generation', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.007, 0, 350, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.0065, 350, 700, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),
         (pepco, rc(pepco, 'R'), 0.005, 700, None, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 6, 1), dt(2014, 9, 1)),

         #Pepco SOS Generation R Jun 1, 2014 - Sept 1, 2014
         (pepco, rc(pepco, 'R'), 0.007, 0, 350, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.0065, 350, 700, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1)),
         (pepco, rc(pepco, 'R'), 0.006, 700, None, 1.01, 'transmission', dt(2014, 5, 1), dt(2014, 9, 1), dt(2015, 1, 1))]:

        session.add(BlockQuote(start_time, end_time, block_min, block_max, escalator, company, rate_class, quote, charge, time_issued, 'xref'))

    #CommitmentPeriodQuotes (non-SOS quotes)
    for (term_months, supplier, rate_class, quote, charge, time_isued) in \
        [#Think energy supply for Pepco
         (6, think, rc(pepco, 'RAD'), 0.10, 'generation', dt(2014, 5, 1)),
         (6, think, rc(pepco, 'RAD'), 0.007, 'transmission', dt(2014, 5, 1)),
         (12, think, rc(pepco, 'RAD'), 0.95, 'generation', dt(2014, 5, 1)),
         (12, think, rc(pepco, 'RAD'), 0.0065, 'transmission', dt(2014, 5, 1)),

         #Hudson energy supply for Pepco
         (6, hudson, rc(pepco, 'RAD'), 0.07, 'generation', dt(2014, 5, 1)),
         (6, hudson, rc(pepco, 'RAD'), 0.007, 'transmission', dt(2014, 5, 1)),
         (12, hudson, rc(pepco, 'RAD'), 0.13, 'generation', dt(2014, 5, 1)),
         (12, hudson, rc(pepco, 'RAD'), 0.007, 'transmission', dt(2014, 5, 1))]:

        session.add(TermQuote(term_months, supplier, rate_class, quote, charge,
            time_issued, 'xref'))
    session.flush()
'''


def create_offer_makers(session):
    log.debug('creating offer_makers')
    session.add_all([BlockOfferMaker(session),
                     TermOfferMaker(session)])
    session.flush()


"""
Proof of concept
"""
def run_poc():
    drop_create_tables()
    session = Session()

    create_companies(session)
    create_quotes(session)
    create_offer_makers(session)

    rate_class = session.query(RateClass).join(Utility).\
        filter(Utility.name == 'Pepco').filter(RateClass.name == 'RAD').\
        filter(RateClass.active == True).one()

    use_periods = [UsePeriod(650, datetime(2013, 9, 1), datetime(2013, 10, 1)),
                   UsePeriod(700, datetime(2013, 10, 1), datetime(2013, 11, 1)),
                   UsePeriod(710, datetime(2013, 11, 1), datetime(2013, 12, 1)),
                   UsePeriod(580, datetime(2013, 12, 1), datetime(2014, 1, 1)),
                   UsePeriod(600, datetime(2014, 1, 1), datetime(2014, 2, 1)),
                   UsePeriod(620, datetime(2014, 2, 1), datetime(2014, 3, 1)),
                   UsePeriod(800, datetime(2014, 3, 1), datetime(2014, 4, 1))]

    offers = []
    for maker in session.query(OfferMaker).filter_by(active=True).all():
        offers.extend(maker.make_offers(rate_class, use_periods))

    print "found %s offers:" % len(offers)
    for offer in offers:
        print offer







