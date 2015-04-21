'''SQLAlchemy model classes specific to Power & Gas go here.
Currently just an example--there are no actual database tables.
'''
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, ForeignKey
from billing.core.model import Base

class Quote(Base):
    '''Fixed-price candidate supply contract.
    '''
    __tablename__ = 'quote'

    id = Column(Integer, primary_key=True)

    # inclusive start and exclusive end of the period during which the
    # customer can start receiving energy from this supplier
    start_from = Column(Integer, nullable=False)
    start_until = Column(Integer, nullable=False)

    # term length in number of utility billing periods
    term_months = Column(Integer, nullable=False)

    # when this quote was received
    date_received = Column(DateTime, nullable=False)

    # inclusive start and exclusive end of the period during which this quote
    # is valid
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=False)

    # fixed price for energy in dollars/kWh
    price = Column(Float, nullable=False)

    # other attributes that may need to be added
    #swing_range (%)
    #swing_penalty_rate (is there just one? how do we determine what it is?)

    # joined-table inheritance
    discriminator = Column(String(50), nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'quote',
        'polymorphic_on': discriminator,
    }

    def __init__(self, start_from=None, start_until=None, term_months=None,
                 date_received=None, valid_from=None, valid_until=None,
                 price=None):
        self.start_from = start_from
        self.start_until = start_until
        self.term_months = term_months
        self.date_received = date_received or datetime.utcnow()
        self.valid_from = valid_from
        self.valid_until = valid_until
        self.price = price

class MatrixQuote(Quote):
    '''Fixed-price candidate supply contract that applies to any customer with
    a particular utility, rate class, and annual total energy usage, taken
    from a daily "matrix" spreadsheet.
    '''
    __tablename__ = 'matrix_quote'

    # lower and upper limits on annual total energy consumption for customers
    # that this quote applies to. nullable because there might be no
    # restrictions on energy usage.
    # (min_volume <= customer's energy consumption < limit_volume)
    min_volume = Column(Float)
    limit_volume = Column(Float)

    quote_id = Column(Integer, ForeignKey('quote.id'), primary_key=True)
    __mapper_args__ = {
        'polymorphic_identity': 'matrixquote',
    }

    def __init__(self, start_from=None, start_until=None, term_months=None,
            date_received=None, valid_from=None, valid_until=None, price=None,
            min_volume=None, limit_volume=None):
        super(MatrixQuote, self).__init__(
            start_from=start_from, start_until=start_until,
            term_months=term_months, date_received=date_received,
            valid_from=valid_from, valid_until=valid_until, price=price)
        self.min_volume = min_volume
        self.limit_volume = limit_volume

    def __str__(self):
        return '\n'.join(['Matrix quote'] +
            ['%s: %s' % (name, value) for name, value in
            self.column_dict().iteritems()] + [''])


