"""
Utility functions to interact with state database
"""
from datetime import datetime, date

import logging
import sqlalchemy
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from sqlalchemy.sql.expression import desc, asc
from sqlalchemy import func
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean
from sqlalchemy.ext.associationproxy import association_proxy

import traceback

from billing.exc import IssuedBillError, RegisterError, ProcessedBillError
from billing.core.model import Base, Address, Register, Session, Evaluation, \
    UtilBill, Customer, Utility
from billing import config

__all__ = [
    'Payment',
    'Reading',
    'ReeBill',
    'ReeBillCharge',
    'StateDB',
    ]

log = logging.getLogger(__name__)


class ReeBill(Base):
    __tablename__ = 'reebill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    sequence = Column(Integer, nullable=False)
    issued = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    issue_date = Column(DateTime)

    # new fields from Mongo
    ree_charge = Column(Float, nullable=False)
    balance_due = Column(Float, nullable=False)
    balance_forward = Column(Float, nullable=False)
    discount_rate = Column(Float, nullable=False)
    due_date = Column(Date)
    late_charge_rate = Column(Float, nullable=False)
    late_charge = Column(Float, nullable=False)
    total_adjustment = Column(Float, nullable=False)
    manual_adjustment = Column(Float, nullable=False)
    payment_received = Column(Float, nullable=False)
    prior_balance = Column(Float, nullable=False)
    ree_value = Column(Float, nullable=False)
    ree_savings = Column(Float, nullable=False)
    email_recipient = Column(String(1000), nullable=True)
    processed = Column(Boolean, default=False)

    billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)

    customer = relationship("Customer", backref=backref('reebills',
        order_by=id))

    billing_address = relationship('Address', uselist=False,
        cascade='all',
        primaryjoin='ReeBill.billing_address_id==Address.id')
    service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='ReeBill.service_address_id==Address.id')

    _utilbill_reebills = relationship('UtilbillReebill', backref='reebill',
        # NOTE: the "utilbill_reebill" table also has ON DELETE CASCADE in
        # the db
        cascade='delete')

    # NOTE on why there is no corresponding 'UtilBill.reebills' attribute: each
    # 'AssociationProxy' has a 'creator', which is a callable that creates a
    # new instance of the intermediate class whenever an instance of the
    # "target" class is appended to the list (in this case, a new instance of
    # 'UtilbillReebill' to hold each UtilBill). the default 'creator' is just
    # the intermediate class itself, which works when that class' constructor
    # has only one argument and that argument is the target class instance. in
    # this case the 'creator' is 'UtilbillReebill' and its __init__ takes one
    # UtilBill as its argument. if there were a bidirectional relationship
    # where 'UtilBill' also had a 'reebills' attribute,
    # UtilbillReebill.__init__ would have to take both a UtilBill and a ReeBill
    # as arguments, so a 'creator' would have to be explicitly specified. for
    # ReeBill it would be something like
    #     creator=lambda u: UtilbillReebill(u, self)
    # and for UtilBill,
    #     creator=lambda r: UtilbillReebill(self, r)
    # but this will not actually work because 'self' is not available in class
    # scope; there is no instance of UtilBill or ReeBill at the time this
    # code is executed. it also does not work to move the code into __init__
    # and assign the 'utilbills' attribute to a particular ReeBill instance
    # or vice versa. there may be a way to make SQLAlchemy do this (maybe by
    # switching to "classical" class-definition style?) but i decided it was
    # sufficient to have only a one-directional relationship from ReeBill to
    # UtilBill.
    utilbills = association_proxy('_utilbill_reebills', 'utilbill')

    @property
    def utilbill(self):
        assert len(self.utilbills) == 1
        return self.utilbills[0]

    # see the following documentation for delete cascade behavior
    charges = relationship('ReeBillCharge', backref='reebill', cascade='all')
    readings = relationship('Reading', backref='reebill', cascade='all')

    def __init__(self, customer, sequence, version=0, discount_rate=None,
                 late_charge_rate=None, billing_address=None,
                 service_address=None, utilbills=[]):
        self.customer = customer
        self.sequence = sequence
        self.version = version
        self.issued = 0
        if discount_rate:
            self.discount_rate = discount_rate
        else:
            self.discount_rate = self.customer.discountrate
        if late_charge_rate:
            self.late_charge_rate = late_charge_rate
        else:
            self.late_charge_rate = self.customer.latechargerate

        self.ree_charge = 0
        self.balance_due = 0
        self.balance_forward = 0
        self.due_date = None
        self.late_charge = 0
        self.total_adjustment = 0
        self.manual_adjustment = 0
        self.payment_received = 0
        self.prior_balance = 0
        self.ree_value = 0
        self.ree_savings = 0
        self.email_recipient = None

        # NOTE: billing/service_address arguments can't be given default value
        # 'Address()' because that causes the same Address instance to be
        # assigned every time.
        self.billing_address = billing_address or Address()
        self.service_address = service_address or Address()

        # supposedly, SQLAlchemy sends queries to the database whenever an
        # association_proxy attribute is accessed, meaning that if
        # 'utilbills' is set before the other attributes above, SQLAlchemy
        # will try to insert the new row too soon, and fail because many
        # fields are still null but the columns are defined as not-null. this
        # can be fixed by setting 'utilbills' last, but there may be a better
        # solution. see related bug:
        # https://www.pivotaltracker.com/story/show/65502556
        self.utilbills = utilbills

    def __repr__(self):
        return '<ReeBill %s-%s-%s, %s, %s utilbills>' % (
            self.customer.account, self.sequence, self.version, 'issued' if
            self.issued else 'unissued', len(self.utilbills))

    def check_editable(self):
        '''Raise a ProcessedBillError or IssuedBillError to prevent editing a
        bill that should not be editable.
        '''
        if self.issued:
            raise IssuedBillError("Can't modify an issued reebill")
        if self.processed:
            raise ProcessedBillError("Can't modify a processed reebill")

    def get_period(self):
        '''Returns period of the first (only) utility bill for this reebill
        as tuple of dates.
        '''
        return self.utilbills[0].period_start, self.utilbills[0].period_end


    def copy_reading_conventional_quantities_from_utility_bill(self):
        """Sets the conventional_quantity of each reading to match the
        corresponding utility bill register quantity."""
        s = Session.object_session(self)
        for reading, register in s.query(Reading, Register).join(Register,
                Reading.register_binding == Register.register_binding). \
                filter(Reading.reebill_id == self.id). \
                filter(Register.utilbill_id == self.utilbill.id).all():
            reading.conventional_quantity = register.quantity

    def replace_readings_from_utility_bill_registers(self, utility_bill):
        """Deletes and replaces the readings using the corresponding utility
        bill registers."""
        s = Session.object_session(self)
        for reading in self.readings:
            s.expunge(reading)
            self.readings.remove(reading)
        for register in utility_bill.registers:
            new_reading = Reading(register.register_binding, "Energy Sold",
                                  register.quantity, 0, "SUM",
                                  register.quantity_units)
            self.readings.append(new_reading)

    def update_readings_from_reebill(self, reebill_readings):
        '''Updates the set of Readings associated with this ReeBill to match
        the list of registers in the given reebill_readings. Readings that do
        not have a register binding that matches a register in the utility bill
        are ignored.
        '''
        session = Session.object_session(self)
        for r in self.readings:
            session.delete(r)
        utilbill_register_bindings = [r.register_binding for r in
                                      self.utilbill.registers]
        self.readings = [Reading(r.register_binding, r.measure, 0,
                0, r.aggregate_function, r.unit) for r in reebill_readings
                if r.register_binding in utilbill_register_bindings]
        session.flush()

    def get_renewable_energy_reading(self, register_binding):
        assert isinstance(register_binding, basestring)
        try:
            reading = next(r for r in self.readings
                           if r.register_binding == register_binding)
        except StopIteration:
            raise ValueError('Unknown register binding "%s"' % register_binding)
        return reading.renewable_quantity

    def get_reading_by_register_binding(self, binding):
        '''Returns the first Reading object found belonging to this ReeBill
        whose 'register_binding' matches 'binding'.
        '''
        try:
            result = next(r for r in self.readings if r.register_binding == binding)
        except StopIteration:
            raise RegisterError('Unknown register binding "%s"' % binding)
        return result

    def set_renewable_energy_reading(self, register_binding, new_quantity):
        assert isinstance(register_binding, basestring)
        assert isinstance(new_quantity, (float, int))
        reading = self.get_reading_by_register_binding(register_binding)
        unit = reading.unit.lower()

        # Thermal: convert quantity to therms according to unit, and add it to
        # the total
        if unit == 'therms':
            new_quantity /= 1e5
        elif unit == 'btu':
            # TODO physical constants must be global
            pass
        elif unit == 'kwh':
            # TODO physical constants must be global
            new_quantity /= 1e5
            new_quantity /= .0341214163
        elif unit == 'ccf':
            # deal with non-energy unit "CCF" by converting to therms with
            # conversion factor 1
            # TODO: 28825375 - need the conversion factor for this
            # print ("Register in reebill %s-%s-%s contains gas measured "
            #        "in ccf: energy value is wrong; time to implement "
            #        "https://www.pivotaltracker.com/story/show/28825375") \
            #       % (self.account, self.sequence, self.version)
            new_quantity /= 1e5
        # PV: Unit is kilowatt; no conversion needs to happen
        elif unit == 'kwd':
            pass
        else:
            raise ValueError('Unknown energy unit: "%s"' % unit)

        reading.renewable_quantity = new_quantity

    def get_total_renewable_energy(self, ccf_conversion_factor=None):
        total_therms = 0
        for reading in self.readings:
            quantity = reading.renewable_quantity
            unit = reading.unit.lower()
            assert isinstance(quantity, (float, int))
            assert isinstance(unit, basestring)

            # convert quantity to therms according to unit, and add it to
            # the total
            if unit == 'therms':
                total_therms += quantity
            elif unit == 'btu':
                # TODO physical constants must be global
                total_therms += quantity / 100000.0
            elif unit == 'kwh':
                # TODO physical constants must be global
                total_therms += quantity / .0341214163
            elif unit == 'ccf':
                if ccf_conversion_factor is not None:
                    total_therms += quantity * ccf_conversion_factor
                else:
                    # TODO: 28825375 - need the conversion factor for this
                    # print ("Register in reebill %s-%s-%s contains gas measured "
                    #        "in ccf: energy value is wrong; time to implement "
                    #        "https://www.pivotaltracker.com/story/show/28825375"
                    #       ) % (self.customer.account, self.sequence,
                    #       self.version)
                    # assume conversion factor is 1
                    total_therms += quantity
            elif unit == 'kwd':
                total_therms += quantity
            else:
                raise ValueError('Unknown energy unit: "%s"' % unit)

        return total_therms

    def get_total_conventional_energy(self, ccf_conversion_factor=None):
        # TODO remove duplicate code with the above
        total_therms = 0
        for reading in self.readings:
            quantity = reading.conventional_quantity
            unit = reading.unit.lower()
            assert isinstance(quantity, (float, int))
            assert isinstance(unit, basestring)

            # convert quantity to therms according to unit, and add it to
            # the total
            if unit == 'therms':
                total_therms += quantity
            elif unit == 'btu':
                # TODO physical constants must be global
                total_therms += quantity / 100000.0
            elif unit == 'kwh':
                # TODO physical constants must be global
                total_therms += quantity / .0341214163
            elif unit == 'ccf':
                if ccf_conversion_factor is not None:
                    total_therms += quantity * ccf_conversion_factor
                else:
                    # TODO: 28825375 - need the conversion factor for this
                    # print ("Register in reebill %s-%s-%s contains gas measured "
                    #        "in ccf: energy value is wrong; time to implement "
                    #        "https://www.pivotaltracker.com/story/show/28825375"
                    #       ) % (self.customer.account, self.sequence,
                    #       self.version)
                    # assume conversion factor is 1
                    total_therms += quantity
            elif unit == 'kwd':
                total_therms += quantity
            else:
                raise ValueError('Unknown energy unit: "%s"' % unit)
        return total_therms

    def replace_charges_with_context_evaluations(self, context):
        """Replace the ReeBill charges with data from each `Evaluation`.
        :param context: a dictionary of binding: `Evaluation`
        """
        for binding in set([r.register_binding for r in self.readings]):
            del context[binding]
        session = Session.object_session(self)
        for charge in self.charges:
            session.delete(charge)
        self.charges = []
        charge_dct = {c.rsi_binding: c for c in self.utilbill.charges}
        for binding, evaluation in context.iteritems():
            charge = charge_dct[binding]
            if charge.has_charge:
                quantity_units = '' if charge.quantity_units is None else charge.quantity_units
                session.add(ReeBillCharge(self, binding, charge.description,
                        charge.group, charge.quantity, evaluation.quantity,
                        quantity_units, charge.rate, charge.total,
                        evaluation.total))

    def compute_charges(self):
        """Computes and updates utility bill charges, then computes and
        updates reebill charges."""
        self.utilbill.compute_charges()
        session = Session.object_session(self)
        for charge in self.charges:
            session.delete(charge)
        context = {r.register_binding: Evaluation(r.hypothetical_quantity)
                   for r in self.readings}
        for charge in self.utilbill.ordered_charges():
            evaluation = charge.evaluate(context, update=False)
            if evaluation.exception is not None:
                raise evaluation.exception
            context[charge.rsi_binding] = evaluation
        self.replace_charges_with_context_evaluations(context)

    def document_id_for_utilbill(self, utilbill):
        '''Returns the id (string) of the "frozen" utility bill document in
        Mongo corresponding to the given utility bill which is attached to this
        reebill. This will be None if this reebill is unissued.'''
        return next(ubrb.document_id for ubrb in self._utilbill_reebills if
                    ubrb.utilbill == utilbill)

    def uprs_id_for_utilbill(self, utilbill):
        '''Returns the id (string) of the "frozen" UPRS document in Mongo
        corresponding to the given utility bill which is attached to this
        reebill. This will be None if this reebill is unissued.'''
        return next(ubrb.uprs_document_id for ubrb in self._utilbill_reebills
                    if ubrb.utilbill == utilbill)

    @property
    def total(self):
        '''The sum of all charges on this bill that do not come from other
        bills, i.e. charges that are being charged to the customer's account on
        this bill's issue date. (This includes the late charge, which depends
        on another bill for its value but belongs to the bill on which it
        appears.) This total is what should be used to calculate the adjustment
        produced by the difference between two versions of a bill.'''
        return self.ree_charge + self.late_charge

    def get_total_actual_charges(self):
        '''Returns sum of "actual" versions of all charges.
        '''
        return sum(charge.a_total for charge in self.charges)

    def get_total_hypothetical_charges(self):
        '''Returns sum of "hypothetical" versions of all charges.
        '''
        return sum(charge.h_total for charge in self.charges)

    def get_service_address_formatted(self):
        return str(self.service_address)

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first ReeBillCharge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

    def column_dict(self):
        period_start , period_end = self.get_period()
        the_dict = super(ReeBill, self).column_dict()
        the_dict.update({
            'account': self.customer.account,
            'mailto': self.customer.bill_email_recipient,
            'hypothetical_total': self.get_total_hypothetical_charges(),
            'actual_total': self.get_total_actual_charges(),
            'billing_address': self.billing_address.column_dict(),
            'service_address': self.service_address.column_dict(),
            'period_start': period_start,
            'period_end': period_end,
            'utilbill_total': sum(u.get_total_charges() for u in self.utilbills),
            # TODO: is this used at all? does it need to be populated?
            'services': [],
            'readings': [r.column_dict() for r in self.readings]
        })

        if self.version > 0:
            if self.issued:
                the_dict['corrections'] = str(self.version)
            else:
                the_dict['corrections'] = '#%s not issued' % self.version
        else:
            the_dict['corrections'] = '-' if self.issued else '(never ' \
                                                                 'issued)'
        # wrong energy unit can make this method fail causing the reebill
        # grid to not load; see
        # https://www.pivotaltracker.com/story/show/59594888
        try:
            the_dict['ree_quantity'] = self.get_total_renewable_energy()
        except (ValueError, StopIteration) as e:
            log.error(
                "Error when getting renewable energy "
                "quantity for reebill %s:\n%s" % (
                self.id, traceback.format_exc()))
            the_dict['ree_quantity'] = 'ERROR: %s' % e.message

        return the_dict


class UtilbillReebill(Base):
    '''Class corresponding to the "utilbill_reebill" table which represents the
    many-to-many relationship between "utilbill" and "reebill".'''
    __tablename__ = 'utilbill_reebill'

    reebill_id = Column(Integer, ForeignKey('reebill.id'), primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), primary_key=True)

    # there is no delete cascade in this 'relationship' because a UtilBill
    # should not be deleted when a UtilbillReebill is deleted.
    utilbill = relationship('UtilBill', backref='_utilbill_reebills')

    def __init__(self, utilbill, document_id=None):
        # UtilbillReebill has only 'utilbill' in its __init__ because the
        # relationship goes Reebill -> UtilbillReebill -> UtilBill. NOTE if the
        # 'utilbill' argument is actually a ReeBill, ReeBill's relationship to
        # UtilbillReebill will cause a stack overflow in SQLAlchemy code
        # (without this check).
        assert isinstance(utilbill, UtilBill)

        self.utilbill = utilbill
        self.document_id = document_id

    def __repr__(self):
        return (('UtilbillReebill(utilbill_id=%s, reebill_id=%s, '
                 'document_id=...%s, uprs_document_id=...%s, ') % (
                    self.utilbill_id, self.reebill_id, self.document_id[-4:],
                    self.uprs_document_id[-4:]))

class ReeBillCharge(Base):
    '''Table representing "hypothetical" versions of charges in reebills (so
    named because these may not have the same schema as utility bill charges).
    Note that, in the past, a set of "hypothetical charges" was associated
    with each utility bill subdocument of a reebill Mongo document, of which
    there was always 1 in practice. Now these charges are associated directly
    with a reebill, so there would be no way to distinguish between charges
    from different utility bills, if there mere multiple utility bills.
    '''
    __tablename__ = 'reebill_charge'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id', ondelete='CASCADE'))
    rsi_binding = Column(String(1000), nullable=False)
    description = Column(String(1000), nullable=False)
    # NOTE alternate name is required because you can't have a column called
    # "group" in MySQL
    group = Column(String(1000), name='group_name', nullable=False)
    a_quantity = Column(Float, nullable=False)
    h_quantity = Column(Float, nullable=False)
    quantity_unit = Column(String(1000), nullable=False)
    rate = Column(Float, nullable=False)
    a_total = Column(Float, nullable=False)
    h_total = Column(Float, nullable=False)

    def __init__(self, reebill, rsi_binding, description, group, a_quantity,
                 h_quantity, quantity_unit, rate, a_total, h_total):
        assert quantity_unit is not None
        self.reebill = reebill
        self.rsi_binding = rsi_binding
        self.description = description
        self.group = group
        self.a_quantity, self.h_quantity = a_quantity, h_quantity
        self.quantity_unit = quantity_unit
        self.rate = rate
        self.a_total, self.h_total = a_total, h_total

class Reading(Base):
    '''Stores utility register readings and renewable energy offsetting the
    value of each register.
    '''
    __tablename__ = 'reading'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id'))

    # identifies which utility bill register this corresponds to
    register_binding = Column(String(1000), nullable=False)

    # name of measure in OLAP database to use for getting renewable energy
    # quantity
    measure = Column(String(1000), nullable=False)

    # actual reading from utility bill
    conventional_quantity = Column(Float, nullable=False)

    # renewable energy offsetting the above
    renewable_quantity = Column(Float, nullable=False)

    aggregate_function = Column(String(15), nullable=False)

    unit = Column(String(1000), nullable=False)

    def __init__(self, register_binding, measure, conventional_quantity,
                 renewable_quantity, aggregate_function, unit):
        assert isinstance(register_binding, basestring)
        assert isinstance(measure, basestring)
        assert isinstance(conventional_quantity, (float, int))
        assert isinstance(renewable_quantity, (float, int))
        assert isinstance(unit, basestring)
        self.register_binding = register_binding
        self.measure = measure
        self.conventional_quantity = conventional_quantity
        self.renewable_quantity = renewable_quantity
        self.aggregate_function = aggregate_function
        self.unit = unit

    def __hash__(self):
        return hash(self.register_binding + self.measure +
                str(self.conventional_quantity) + str(self.renewable_quantity)
                + self.aggregate_function + self.unit)

    def __eq__(self, other):
        return all([
            self.register_binding == other.register_binding,
            self.measure == other.measure,
            self.conventional_quantity == other.conventional_quantity,
            self.renewable_quantity == other.renewable_quantity,
            self.aggregate_function == other.aggregate_function,
            self.unit == other.unit
        ])

    @property
    def hypothetical_quantity(self):
        return self.conventional_quantity + self.renewable_quantity

class Payment(Base):
    __tablename__ = 'payment'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    reebill_id = Column(Integer, ForeignKey('reebill.id'))
    date_received = Column(DateTime, nullable=False)
    date_applied = Column(DateTime, nullable=False)
    description = Column(String(45))
    credit = Column(Float)

    customer = relationship("Customer", backref=backref('payments',
        order_by=id))

    reebill = relationship("ReeBill", backref=backref('payments',
        order_by=id))

    '''date_received is the datetime when the payment was recorded.
    date_applied is the date that the payment is "for", from the customer's
    perspective. Normally these are on the same day, but an error in an old
    payment can be corrected by entering a new payment with the same
    date_applied as the old one, whose credit is the true amount minus the
    previously-entered amount.'''

    def __init__(self, customer, date_received, date_applied, description,
                 credit):
        assert isinstance(date_received, datetime)
        assert isinstance(date_applied, date)
        self.customer = customer
        self.date_received = date_received
        self.date_applied = date_applied
        self.description = description
        self.credit = credit

    def is_editable(self):
        """ Returns True or False depending on whether the payment should be
        editable. Payments should be editable as long as it is not applied to
        a reebill
        """
        today = datetime.utcnow()
        if self.reebill_id is None:
            return True
        return False

    def __repr__(self):
        return '<Payment(%s, received=%s, applied=%s, %s, %s)>' \
               % (self.customer.account, self.date_received, \
                  self.date_applied, self.description, self.credit)

    def column_dict(self):
        the_dict = super(Payment, self).column_dict()
        the_dict.update(editable=self.is_editable())
        return the_dict

class StateDB(object):
    """A Data Access Class"""

    def __init__(self, logger=None):
        """Construct a new :class:`.StateDB`.

        :param session: a ``scoped_session`` instance
        :param logger: a logger object
        """
        self.logger = logger
        self.session = Session

    def get_customer(self, account):
        session = Session()
        return session.query(Customer).filter(Customer.account == account).one()

    def get_utilbill(self, account, service, start, end):
        session = Session()
        customer = session.query(Customer) \
            .filter(Customer.account == account).one()
        return session.query(UtilBill) \
            .filter(UtilBill.customer_id == customer.id) \
            .filter(UtilBill.service == service) \
            .filter(UtilBill.period_start == start) \
            .filter(UtilBill.period_end == end).one()

    def get_create_utility(self, utility_name):
        session = Session()
        try:
            utility = session.query(Utility).filter_by(name=utility_name).one()
        except NoResultFound:
            utility = Utility(utility_name, Address('', '', '', '', ''), '')
        return utility

    def get_utilbill_by_id(self, ubid):
        session = Session()
        return session.query(UtilBill).filter(UtilBill.id == ubid).one()

    def max_version(self, account, sequence):
        # surprisingly, it is possible to filter a ReeBill query by a Customer
        # column even without actually joining with Customer. because of
        # func.max, the result is a tuple rather than a ReeBill object.
        session = Session()
        reebills_subquery = session.query(ReeBill).join(Customer) \
            .filter(ReeBill.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(ReeBill.sequence == sequence)
        max_version = session.query(func.max(
            reebills_subquery.subquery().columns.version)).one()[0]
        # SQLAlchemy returns None when the reebill row doesn't exist, but that
        # should be reported as an exception
        if max_version == None:
            raise NoResultFound

        # SQLAlchemy returns a "long" here for some reason, so convert to int
        return int(max_version)

    def max_issued_version(self, account, sequence):
        '''Returns the greatest version of the given reebill that has been
        issued. (This should differ by at most 1 from the maximum version
        overall, since a new version can't be created if the last one hasn't
        been issued.) If no version has ever been issued, returns None.'''
        # weird filtering on other table without a join
        session = Session()
        customer = self.get_customer(account)
        result = session.query(func.max(ReeBill.version)) \
            .filter(ReeBill.customer == customer) \
            .filter(ReeBill.issued == 1).one()[0]
        # SQLAlchemy returns None if no reebills with that customer are issued
        if result is None:
            return None
        # version number is a long, so convert to int
        return int(result)

    # TODO rename to something like "create_next_version"
    def increment_version(self, account, sequence):
        '''Creates a new reebill with version number 1 greater than the highest
        existing version for the given account and sequence.

        The utility bill(s) of the new version are the same as those of its
        predecessor, but utility bill, UPRS, and document_ids are cleared
        from the utilbill_reebill table, meaning that the new reebill's
        utilbill/UPRS documents are the current ones.

        Returns the new state.ReeBill object.'''
        # highest existing version must be issued
        session = Session()
        current_max_version_reebill = self.get_reebill(account, sequence)
        if current_max_version_reebill.issued != 1:
            raise ValueError(("Can't increment version of reebill %s-%s "
                    "because version %s is not issued yet") % (account,
                    sequence, current_max_version_reebill.version))

        new_reebill = ReeBill(current_max_version_reebill.customer, sequence,
            current_max_version_reebill.version + 1,
            discount_rate=current_max_version_reebill.discount_rate,
            late_charge_rate=current_max_version_reebill.late_charge_rate,
            utilbills=current_max_version_reebill.utilbills)
        for ur in new_reebill._utilbill_reebills:
            ur.document_id, ur.uprs_id, = None, None

        session.add(new_reebill)
        return new_reebill

    def get_unissued_corrections(self, account):
        '''Returns a list of (sequence, version) pairs for bills that have
        versions > 0 that have not been issued.'''
        session = Session()
        reebills = session.query(ReeBill).join(Customer) \
            .filter(Customer.account == account) \
            .filter(ReeBill.version > 0) \
            .filter(ReeBill.issued == 0).all()
        return [(int(reebill.sequence), int(reebill.version)) for reebill
                in reebills]

    def last_sequence(self, account):
        '''Returns the discount rate for the customer given by account.'''
        session = Session()
        result = session.query(Customer).filter_by(account=account).one(). \
            get_discount_rate()
        return result

    def last_sequence(self, account):
        '''Returns the sequence of the last reebill for 'account', or 0 if
        there are no reebills.'''
        session = Session()
        customer = self.get_customer(account)
        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
            .filter(ReeBill.customer_id == customer.id).one()[0]
        # TODO: because of the way 0.xml templates are made (they are not in
        # the database) reebill needs to be primed otherwise the last sequence
        # for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    def last_issued_sequence(self, account,
                             include_corrections=False):
        '''Returns the sequence of the last issued reebill for 'account', or 0
        if there are no issued reebills.'''
        session = Session()
        customer = self.get_customer(account)
        if include_corrections:
            filter_logic = sqlalchemy.or_(ReeBill.issued == 1,
                sqlalchemy.and_(ReeBill.issued == 0, ReeBill.version > 0))
        else:
            filter_logic = ReeBill.issued == 1

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
            .filter(ReeBill.customer_id == customer.id) \
            .filter(filter_logic).one()[0]
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    def get_accounts_grid_data(self, account=None):
        '''Returns the Account, fb_utility_name, fb_rate_class,
        and fb_service_address of every customer,
        the Sequence, Version and Issue date of the highest-sequence,
        highest-version issued ReeBill object,
        the rate class, the service address of the latest
        (i.e. last-ending ) utility bill for each customer, and the period_end
        of the latest *processed* utility bill
        If account is given, the query is filtered by it.
        This is a way of speeding up the AccountsGrid in the UI
        '''
        session = Session()
        sequence_sq = session.query(
            ReeBill.customer_id, func.max(
                ReeBill.sequence).label('max_sequence'))\
            .filter(ReeBill.issued == 1)\
            .group_by(ReeBill.customer_id).subquery()
        version_sq = session.query(
            ReeBill.customer_id, ReeBill.sequence, ReeBill.issue_date,
            func.max(ReeBill.version).label('max_version'))\
            .filter(ReeBill.issued == 1)\
            .group_by(ReeBill.sequence, ReeBill.customer_id)\
            .subquery()
        utilbill_sq = session.query(
            UtilBill.customer_id,
            func.max(UtilBill.period_end).label('max_period_end'))\
        .group_by(UtilBill.customer_id)\
        .subquery()
        processed_utilbill_sq = session.query(
            UtilBill.customer_id,
            func.max(UtilBill.period_end).label('max_period_end_processed'))\
        .filter(UtilBill.processed == 1)\
        .group_by(UtilBill.customer_id)\
        .subquery()

        q = session.query(Customer.account,
                          Utility.name,
                          Customer.fb_rate_class,
                          Customer.fb_service_address,
                          sequence_sq.c.max_sequence,
                          version_sq.c.max_version,
                          version_sq.c.issue_date,
                          UtilBill.rate_class,
                          Address,
                          processed_utilbill_sq.c.max_period_end_processed)\
        .outerjoin(Utility, Utility.id == Customer.fb_utility_id)\
        .outerjoin(sequence_sq, Customer.id == sequence_sq.c.customer_id)\
        .outerjoin(version_sq, and_(Customer.id == version_sq.c.customer_id,
                   sequence_sq.c.max_sequence == version_sq.c.sequence))\
        .outerjoin(utilbill_sq, Customer.id == utilbill_sq.c.customer_id)\
        .outerjoin(UtilBill, and_(
            UtilBill.customer_id == utilbill_sq.c.customer_id,
            UtilBill.period_end == utilbill_sq.c.max_period_end))\
        .outerjoin(Address, UtilBill.service_address_id == Address.id)\
        .outerjoin(processed_utilbill_sq,
                   Customer.id == processed_utilbill_sq.c.customer_id)\
        .order_by(desc(Customer.account))

        if account is not None:
            q = q.filter(Customer.account == account)

        return q.all()

    def issue(self, account, sequence, issue_date=None):
        '''Marks the highest version of the reebill given by account, sequence
        as issued.
        '''
        reebill = self.get_reebill(account, sequence)
        if issue_date is None:
            issue_date = datetime.utcnow()
        if reebill.issued == 1:
            raise IssuedBillError(("Can't issue reebill %s-%s-%s because it's "
                    "already issued") % (account, sequence, reebill.version))
        reebill.issued = 1
        reebill.processed = 1
        reebill.issue_date = issue_date

    def is_issued(self, account, sequence, version='max',
                  nonexistent=None):
        '''Returns true if the reebill given by account, sequence, and version
        (latest version by default) has been issued, false otherwise. If
        'nonexistent' is given, that value will be returned if the reebill is
        not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        # NOTE: with the old database schema (one reebill row for all versions)
        # this method returned False when the 'version' argument was higher
        # than max_version. that was probably the wrong behavior, even though
        # test_state:StateDBTest.test_versions tested for it.
        session = Session()
        try:
            if version == 'max':
                reebill = self.get_reebill(account, sequence)
            elif isinstance(version, int):
                reebill = self.get_reebill(account, sequence, version)
            else:
                raise ValueError('Unknown version specifier "%s"' % version)
            # NOTE: reebill.issued is an int, and it converts the entire
            # expression to an int unless explicitly cast! see
            # https://www.pivotaltracker.com/story/show/35965271
            return bool(reebill.issued == 1)
        except NoResultFound:
            if nonexistent is not None:
                return nonexistent
            raise

    def account_exists(self, account):
        session = Session()
        try:
           session.query(Customer).with_lockmode("read")\
                .filter(Customer.account == account).one()
        except NoResultFound:
            return False
        return True

    def listAccounts(self):
        '''List of all customer accounts (ordered).'''
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        session = Session()
        result = map((lambda x: x[0]),
            session.query(Customer.account) \
                .order_by(Customer.account).all())
        return result

    def listSequences(self, account):
        session = Session()

        # TODO: figure out how to do this all in one query. many SQLAlchemy
        # subquery examples use multiple queries but that shouldn't be
        # necessary
        customer = session.query(Customer).filter(
            Customer.account == account).one()
        sequences = session.query(ReeBill.sequence).with_lockmode("read") \
            .filter(ReeBill.customer_id == customer.id).all()

        # sequences is a list of tuples of numbers, so convert it into a plain list
        result = map((lambda x: x[0]), sequences)

        return result

    def listReebills(self, start, limit, account, sort, dir, **kwargs):
        session = Session()
        query = session.query(ReeBill).join(Customer) \
            .filter(Customer.account == account)

        if (dir == u'DESC'):
            order = desc
        elif (dir == u'ASC'):
            order = asc
        else:
            raise ValueError(
                "Bad Parameter Value: 'dir' must be 'ASC' or 'DESC'")

        if (sort == u'sequence'):
            field = ReeBill.sequence
        else:
            raise ValueError("Bad Parameter Value: 'sort' must be 'sequence'")

        slice = query.order_by(order(field))[start:start + limit]
        count = query.count()

        return slice, count

    def reebills(self, include_unissued=True):
        '''Generates (account, sequence, max version) tuples for all reebills
        in MySQL.'''
        for account in self.listAccounts():
            for sequence in self.listSequences(account):
                reebill = self.get_reebill(account, sequence)
                if include_unissued or reebill.issued:
                    yield account, int(sequence), int(reebill.max_version)

    def get_reebill(self, account, sequence, version='max'):
        '''Returns the ReeBill object corresponding to the given account,
        sequence, and version (the highest version if no version number is
        given).'''
        session = Session()
        if version == 'max':
            version = session.query(func.max(ReeBill.version)).join(Customer) \
                .filter(Customer.account == account) \
                .filter(ReeBill.sequence == sequence).one()[0]
        result = session.query(ReeBill).join(Customer) \
            .filter(Customer.account == account) \
            .filter(ReeBill.sequence == sequence) \
            .filter(ReeBill.version == version).one()
        return result

    def get_reebill_by_id(self, rbid):
        session = Session()
        return session.query(ReeBill).filter(ReeBill.id == rbid).one()

    def list_utilbills(self, account, start=None, limit=None):
        '''Queries the database for account, start date, and end date of bills
        in a slice of the utilbills table; returns the slice and the total
        number of rows in the table (for paging). If 'start' is not given, all
        bills are returned. If 'start' is given but 'limit' is not, all bills
        starting with index 'start'. If both 'start' and 'limit' are given,
        returns bills with indices in [start, start + limit).'''
        session = Session()
        query = session.query(UtilBill).with_lockmode('read').join(Customer) \
            .filter(Customer.account == account) \
            .order_by(Customer.account, desc(UtilBill.period_start))

        if start is None:
            return query, query.count()
        if limit is None:
            return query[start:], query.count()
        return query[start:start + limit], query.count()

    def create_payment(self, account, date_applied, description,
                       credit, date_received=None):
        '''Adds a new payment, returns the new Payment object. By default,
        'date_received' is the current datetime in UTC when this method is
        called; only override this for testing purposes.'''
        # NOTE a default value for 'date_received' can't be specified as a
        # default argument in the method signature because it would only get
        # evaluated once at the time this module was imported, which means its
        # value would be the same every time this method is called.
        if date_received is None:
            date_received = datetime.utcnow()
        session = Session()
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        new_payment = Payment(customer, date_received, date_applied,
                description, credit)
        session.add(new_payment)
        session.flush()
        return new_payment

    def delete_payment(self, oid):
        '''Deletes the payment with id 'oid'.'''
        session = Session()
        payment = session.query(Payment).filter(Payment.id == oid).one()
        session.delete(payment)

    def find_payment(self, account, periodbegin, periodend):
        '''Returns a list of payment objects whose date_applied is in
        [periodbegin, period_end).'''
        # periodbegin and periodend must be non-overlapping between bills. This
        # is in direct opposition to the reebill period concept, which is a
        # period that covers all services for a given reebill and thus overlap
        # between bills.  Therefore, a non overlapping period could be just the
        # first utility service on the reebill. If the periods overlap,
        # payments will be applied more than once. See 11093293
        session = Session()
        payments = session.query(Payment) \
            .filter(Payment.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(and_(Payment.date_applied >= periodbegin,
            Payment.date_applied < periodend)).all()
        return payments

    def get_total_payment_since(self, account, start, end=None, payment_objects=False):
        '''Returns sum of all account's payments applied on or after 'start'
        and before 'end' (today by default). If 'start' is None, the beginning
        of the interval extends to the beginning of time.
        '''
        assert isinstance(start, datetime)
        if end is None:
            end=datetime.utcnow()
        session = Session()
        payments = session.query(Payment)\
                .filter(Payment.customer==self.get_customer(account))\
                .filter(Payment.date_applied < end)
        if start is not None:
            payments = payments.filter(Payment.date_applied >= start)
        if payment_objects:
            return payments.all()
        return float(sum(payment.credit for payment in payments.all()))

    def payments(self, account):
        '''Returns list of all payments for the given account ordered by
        date_received.'''
        session = Session()
        payments = session.query(Payment).join(Customer) \
            .filter(Customer.account == account).order_by(
            Payment.date_received).all()
        return payments


