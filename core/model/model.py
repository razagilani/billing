'''
SQLALchemy classes for all applications that use the utility bill database.
Also contains some related classes that do not correspond to database tables.
'''
import ast
from datetime import datetime, timedelta
import json

import sqlalchemy
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm.interfaces import MapperExtension
from sqlalchemy.orm import sessionmaker, scoped_session, object_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean, \
    Enum
from sqlalchemy.ext.declarative import declarative_base
import tsort
from alembic.migration import MigrationContext

from exc import FormulaSyntaxError, FormulaError, DatabaseError, \
    ProcessedBillError


__all__ = [
    'Address',
    'Base',
    'Charge',
    'ChargeEvaluation',
    'Evaluation',
    'MYSQLDB_DATETIME_MIN',
    'Register',
    'Session',
    'Supplier',
    'RateClass',
    'Utility',
    'UtilBill',
    'UtilityAccount',
    'check_schema_revision',
]

# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900, 1, 1)

Session = scoped_session(sessionmaker())

class Base(object):
    '''Common methods for all SQLAlchemy model classes, for use both here
    and in consumers that define their own model classes.
    '''
    @classmethod
    def column_names(cls):
        '''Return list of attributes in the class that correspond to
        database columns.
        '''
        return [prop.key for prop in class_mapper(cls).iterate_properties
                if isinstance(prop, sqlalchemy.orm.ColumnProperty)]

    def __eq__(self, other):
        if not isinstance(other, Base):
            return False
        return all([getattr(self, x) == getattr(other, x) for x in
                    self.column_names()])

    def column_dict(self):
        '''Return dictionary of names and values for all attributes
        corresponding to database columns.
        '''
        return {c: getattr(self, c) for c in self.column_names()}
Base = declarative_base(cls=Base)


_schema_revision = '572b9c75caf3'
def check_schema_revision(schema_revision=None):
    """Checks to see whether the database schema revision matches the
    revision expected by the model metadata.
    """
    schema_revision = schema_revision or _schema_revision
    s = Session()
    conn = s.connection()
    context = MigrationContext.configure(conn)
    current_revision = context.get_current_revision()
    if current_revision != schema_revision:
        raise DatabaseError("Database schema revision mismatch."
                            " Require revision %s; current revision %s"
                            % (schema_revision, current_revision))

class Callback(MapperExtension):
    def before_update(self, mapper, connection, instance):
        if object_session(instance).is_modified(instance, include_collections=False):
            instance.date_modified = datetime.now()

class Evaluation(object):
    """A data structure to hold inputs for calculating charges. It can hold
    the value of a `Register` or the result of evaluating a `Charge`.
    """
    def __init__(self, quantity):
        self.quantity = quantity

class ChargeEvaluation(Evaluation):
    """An `Evaluation to store the result of evaluating a `Charge`.
    """
    def __init__(self, quantity=None, rate=None, exception=None):
        super(ChargeEvaluation, self).__init__(quantity)
        assert quantity is None or isinstance(quantity, (float, int))
        assert rate is None or isinstance(rate, (float, int))

        # when there's an error, quantity and rate should both be None
        if None in (quantity, rate):
            assert exception is not None
            quantity = rate = None
            self.total = None
        else:
            assert exception is None
            self.total = quantity * rate

        self.quantity = quantity
        self.rate = rate
        self.exception = exception

class Address(Base):
    __tablename__ = 'address'

    id = Column(Integer, primary_key=True)
    addressee = Column(String(1000), nullable=False)
    street = Column(String(1000), nullable=False)
    city = Column(String(1000), nullable=False)
    state = Column(String(1000), nullable=False)
    postal_code = Column(String(1000), nullable=False)

    def __init__(self, addressee='', street='', city='', state='',
                 postal_code=''):
        self.addressee = addressee
        self.street = street
        self.city = city
        self.state = state
        self.postal_code = postal_code

    @classmethod
    def from_other(cls, other_address):
        """Constructs a new :class:`.Address` instance whose attributes are
        copied from the given `other_address`.
        :param other_address: An :class:`.Address` instance from which to
         copy attributes.
        """
        assert isinstance(other_address, cls)
        return cls(other_address.addressee,
            other_address.street,
            other_address.city,
            other_address.state,
            other_address.postal_code)

    def __hash__(self):
        return hash(self.addressee + self.street + self.city +
                    self.postal_code)

    def __repr__(self):
        return 'Address<(%s, %s, %s, %s, %s)' % (self.addressee, self.street,
                self.city, self.state, self.postal_code)

    def __str__(self):
        return '%s, %s, %s' % (self.street, self.city, self.state)

    def column_dict(self):
        raise NotImplementedError

    # TODO rename to column_dict
    def to_dict(self):
        return {
            #'id': self.id,
            'addressee': self.addressee,
            'street': self.street,
            'city': self.city,
            'state': self.state,
            'postal_code': self.postal_code,
        }

    @classmethod
    def from_other(cls, other_address):
        """Constructs a new :class:`.Address` instance whose attributes are
        copied from the given `other_address`.
        :param other_address: An :class:`.Address` instance from which to
         copy attributes.
        """
        assert isinstance(other_address, cls)
        return cls(other_address.addressee,
                   other_address.street,
                   other_address.city,
                   other_address.state,
                   other_address.postal_code)


class Utility(Base):
    '''A company that distributes energy and is responsible for the distribution
    charges on utility bills.
    '''
    __tablename__ = 'utility'

    id = Column(Integer, primary_key=True)
    address_id = Column(Integer, ForeignKey('address.id'))

    name = Column(String(1000), nullable=False)
    address = relationship("Address")

    def __init__(self, name, address):
        self.name = name
        self.address = address

    def __repr__(self):
        return '<Utility(%s)>' % self.name

    def __str__(self):
        return self.name


class Supplier(Base):
    '''A company that supplies energy and is responsible for the supply
    charges on utility bills. This may be the same as the utility in the
    case of SOS.
    '''
    __tablename__ = 'supplier'
    id = Column(Integer, primary_key=True)
    name = Column(String(1000), nullable=False)

    address_id = Column(Integer, ForeignKey('address.id'))
    address = relationship("Address")

    def __init__(self, name, address):
        self.name = name
        self.address = address

    def __repr__(self):
        return '<Supplier(%s)>' % self.name

    def __str__(self):
        return self.name


class RateClass(Base):
    '''Represents a group of utility accounts that all have the same utility
    and the same pricing for distribution and SOS supply. The rate class also
    determines what supply contracts may be available to a customer for
    non-SOS supply.
    '''
    __tablename__ = 'rate_class'

    id = Column(Integer, primary_key=True)
    utility_id = Column(Integer, ForeignKey('utility.id'), nullable=False)
    name = Column(String(255), nullable=False)

    utility = relationship('Utility')

    def __init__(self, name, utility):
        self.name = name
        self.utility = utility

    def __repr__(self):
        return '<RateClass(%s)>' % self.name

    def __str__(self):
        return self.name


class UtilityAccount(Base):
    __tablename__ = 'utility_account'

    id = Column(Integer, primary_key = True)
    name = Column(String(45))

    # account number used by the utility, shown on utility bills and
    # the utility's website. (also used as an inter-database foreign key for
    # referring to UtilityAccounts from other databases, because it can be
    # reasonably be expected to be permanent and unique.)
    account_number = Column(String(1000), nullable=False)

    # Nextility account number, which is currently only used for ReeBill.
    # this is shown to customers on their solar energy bills from Nextility.
    account = Column(String(45), nullable=False)

    # "fb_" = to be assigned to the utility_account's first-created utility bill
    fb_utility_id = Column(Integer, ForeignKey('utility.id'))
    fb_rate_class_id = Column(Integer, ForeignKey('rate_class.id'),
        nullable=True)
    fb_billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    fb_service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    fb_supplier_id = Column(Integer, ForeignKey('supplier.id'),
        nullable=True)

    fb_supplier = relationship('Supplier', uselist=False,
        primaryjoin='UtilityAccount.fb_supplier_id==Supplier.id')
    fb_rate_class = relationship('RateClass', uselist=False,
        primaryjoin='UtilityAccount.fb_rate_class_id==RateClass.id')
    fb_billing_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilityAccount.fb_billing_address_id==Address.id')
    fb_service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilityAccount.fb_service_address_id==Address.id')
    fb_utility = relationship('Utility')

    def __init__(self, name, account, fb_utility, fb_supplier,
                fb_rate_class, fb_billing_address, fb_service_address,
                account_number=''):
        """Construct a new :class:`.Customer`.
        :param name: The name of the utility_account.
        :param account:
        :fb_utility: The :class:`.Utility` to be assigned to the the first
        `UtilityBill` associated with this utility_account.
        :fb_supplier: The :class: 'Supplier' to be assigned to the first
        'UtilityBill' associated with this utility_account
        :fb_rate_class": "first bill rate class" (see fb_utility_name)
        :fb_billing_address: (as previous)
        :fb_service address: (as previous)
        """
        self.name = name
        self.account_number = account_number
        self.account = account
        self.fb_utility = fb_utility
        self.fb_supplier = fb_supplier
        self.fb_rate_class = fb_rate_class
        self.fb_billing_address = fb_billing_address
        self.fb_service_address = fb_service_address


    def __repr__(self):
        return '<utility_account(name=%s, account=%s)>' \
               % (self.name, self.account)


class UtilBill(Base):
    __tablename__ = 'utilbill'
    __mapper_args__ = {'extension':Callback()}

    id = Column(Integer, primary_key=True)

    utility_id = Column(Integer, ForeignKey('utility.id'), nullable=False)
    billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    supplier_id = Column(Integer, ForeignKey('supplier.id'),
        nullable=True)
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
        nullable=False)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'),
        nullable=True)

    state = Column(Integer, nullable=False)
    service = Column(String(45), nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    due_date = Column(Date)

    # optional, total of charges seen in PDF: user knows the bill was processed
    # correctly when the calculated total matches this number
    target_total = Column(Float)

    date_received = Column(DateTime)
    date_modified = Column(DateTime)
    account_number = Column(String(1000), nullable=False)
    sha256_hexdigest = Column(String(64), nullable=False)

    # whether this utility bill is considered "done" by the user--mainly
    # meaning that its rate structure and charges are supposed to be accurate
    # and can be relied upon for rate structure prediction
    processed = Column(Integer, nullable=False)

    # date when a process was run to extract data from the bill file to fill in
    # data automatically. (note this is different from data scraped from the
    # utility web site, because that can only be done while the bill is being
    # downloaded and can't take into account information from other sources.)
    # TODO: not being used at all
    date_scraped = Column(DateTime)

    # cascade for UtilityAccount relationship does NOT include "save-update"
    # to allow more control over when UtilBills get added--for example,
    # when uploading a new utility bill, the new UtilBill object should only
    # be added to the session after the file upload succeeded (because in a
    # test, there is no way to check that the UtilBill was not inserted into
    # the database because the transaction was rolled back).
    utility_account = relationship("UtilityAccount", backref=backref('utilbill',
            order_by=id, cascade='delete'))

    supplier = relationship('Supplier', uselist=False,
        primaryjoin='UtilBill.supplier_id==Supplier.id')
    rate_class = relationship('RateClass', uselist=False,
        primaryjoin='UtilBill.rate_class_id==RateClass.id')
    billing_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.billing_address_id==Address.id')
    service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.service_address_id==Address.id')
    utility = relationship('Utility')

    @staticmethod
    def validate_utilbill_period(start, end):
        '''Raises an exception if the dates 'start' and 'end' are unreasonable
        as a utility bill period: "reasonable" means start < end and (end -
        start) < 1 year. Does nothing if either period date is None.
        '''
        if None in (start, end):
            return
        if start >= end:
            raise ValueError('Utility bill start date must precede end')
        if (end - start).days > 365:
            raise ValueError('Utility billing period lasts longer than a year')

    # utility bill states:
    # 0. Complete: actual non-estimated utility bill.
    # 1. Utility estimated: actual utility bill whose contents were estimated by
    # the utility (and which will be corrected later to become Complete).
    # 2. Estimated: a bill that is known to exist (and whose dates are
    # correct) but whose contents were estimated (not by the utility).
    # 3. Hypothetical: it is believed that there is probably a bill during a
    # certain time period and estimates what its contents would be if it
    # existed. Such a bill may not really exist (since we can't even know how
    # many bills there are in a given period of time), and if it does exist,
    # its actual dates will probably be different than the guessed ones.
    # TODO 38385969: not sure this strategy is a good idea
    Complete, UtilityEstimated, Estimated = range(3)

    # human-readable names for utilbill states (used in UI)
    _state_descriptions = {
        Complete: 'Final',
        UtilityEstimated: 'Utility Estimated',
        Estimated: 'Estimated',
    }

    # TODO remove uprs_id, doc_id
    def __init__(self, utility_account, state, service, utility, supplier, rate_class,
                 billing_address, service_address, period_start=None,
                 period_end=None, doc_id=None, uprs_id=None,
                 target_total=0, date_received=None, processed=False,
                 reebill=None, sha256_hexdigest='', due_date=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.Estimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.utility_account = utility_account
        self.state = state
        self.service = service
        self.utility = utility
        self.rate_class = rate_class
        self.supplier = supplier
        self.billing_address = billing_address
        self.service_address = service_address
        self.period_start = period_start
        self.period_end = period_end
        self.target_total = target_total
        self.date_received = date_received
        self.account_number = utility_account.account_number
        self.processed = processed
        self.document_id = doc_id
        self.uprs_document_id = uprs_id
        self.due_date = due_date

        # TODO: empty string as default value for sha256_hexdigest is
        # probably a bad idea. if we are writing tests that involve puttint
        # UtilBills in an actual database then we should probably have actual
        # files for them.
        self.sha256_hexdigest = sha256_hexdigest

        self.date_modified = datetime.utcnow()

    def state_name(self):
        return self.__class__._state_descriptions[self.state]

    def get_utility(self):
        # the 'utility' attribute may move to UtilityAccount where it would
        # make more sense for it to be.
        return self.utility

    def get_supplier(self):
        # the 'supplier' attribute may move to UtilityAccount where it would
        # make more sense for it to be.
        return self.supplier

    def get_utility_name(self):
        '''Return name of this bill's utility.
        '''
        return self.utility.name

    def get_estimated_next_meter_read_date(self):
        '''Return approximate date of next meter read (which is usually the
        end date of the next utility bill after this one), or None if no
        estimate can be made.
        '''
        if self.period_end is None:
            return None
        return self.period_end + timedelta(days=30)

    def get_rate_class_name(self):
        '''Return name of this bill's rate class or None if the rate class is
        None (unknown).
        '''
        if self.rate_class is None:
            return None
        return self.rate_class.name

    def get_supplier_name(self):
        '''Return name of this bill's supplier or None if the supplier is
        None (unknown).
        '''
        if self.supplier is None:
            return None
        return self.supplier.name

    def get_nextility_account_number(self):
        '''Return the "nextility account number" (e.g.  "10001") not to be
        confused with utility account number. This  may go away since it is
        only used for ReeBill but it was part of Kris' schema for CSV files
        of data exported to the  Altitude database.
        '''
        return self.utility_account.account

    def get_utility_account_number(self):
        return self.utility_account.account_number

    def __repr__(self):
        return ('<UtilBill(utility_account=<%s>, service=%s, period_start=%s, '
                'period_end=%s, state=%s)>') % (
            self.utility_account.account, self.service, self.period_start,
            self.period_end, self.state)

    def is_attached(self):
        return len(self._utilbill_reebills) > 0

    def add_charge(self, **charge_kwargs):
        session = Session.object_session(self)
        all_rsi_bindings = set([c.rsi_binding for c in self.charges])
        n = 1
        while ('New Charge %s' % n) in all_rsi_bindings:
            n += 1
        charge = Charge(utilbill=self,
                        rsi_binding=charge_kwargs.get(
                            'rsi_binding', "New Charge %s" % n),
                        rate=charge_kwargs.get('rate', 0.0),
                        quantity_formula=charge_kwargs.get(
                            'quantity_formula', ''),
                        description=charge_kwargs.get(
                            'description',
                            "New Charge - Insert description here"),
                        group=charge_kwargs.get("group", ''),
                        unit=charge_kwargs.get('unit', "dollars"),
                        type=charge_kwargs.get('type', "supply")
                        )
        session.add(charge)
        registers = self.registers
        charge.quantity_formula = '' if len(registers) == 0 else \
            'REG_TOTAL.quantity' if any([register.register_binding ==
                'REG_TOTAL' for register in registers]) else \
            registers[0].register_binding
        session.flush()
        return charge

    def ordered_charges(self):
        """Sorts the charges by their evaluation order. Any charge that is
        part part of a cycle is put at the start of the list so it will get
        an error when evaluated.
        """
        depends = {}
        for c in self.charges:
            try:
                depends[c.rsi_binding] = c.formula_variables()
            except SyntaxError:
                depends[c.rsi_binding] = set()
        dependency_graph = []
        independent_bindings = set(depends.keys())

        for binding, depended_bindings in depends.iteritems():
            for depended_binding in depended_bindings:
                #binding depends on depended_binding
                dependency_graph.append((depended_binding, binding))
                independent_bindings.discard(binding)
                independent_bindings.discard(depended_binding)

        while True:
            try:
                sortresult = tsort.topological_sort(dependency_graph)
            except tsort.GraphError as g:
                circular_bindings = set(g.args[1])
                independent_bindings.update(circular_bindings)
                dependency_graph = [(a, b) for a, b in dependency_graph
                                    if b not in circular_bindings]
            else:
                break
        order = list(independent_bindings) + [x for x in sortresult
                if x not in independent_bindings]
        return sorted(self.charges, key=lambda x: order.index(x.rsi_binding))

    def compute_charges(self, raise_exception=False):
        """Computes and updates the quantity, rate, and total attributes of
        all charges associated with `UtilBill`.
        :param raise_exception: Raises an exception if any charge could not be
        computed. Otherwise silently sets the error attribute of the charge
        to the exception message.
        """
        context = {r.register_binding: Evaluation(r.quantity) for r in
                   self.registers}
        sorted_charges = self.ordered_charges()
        exception = None
        for charge in sorted_charges:
            evaluation = charge.evaluate(context, update=True)
            # only charges that do not have errors get added to 'context'
            if evaluation.exception is None:
                context[charge.rsi_binding] = evaluation
            elif exception is None:
                exception = evaluation.exception

        # all charges should be computed before the exception is raised
        if raise_exception and exception:
            raise exception

    def editable(self):
        if self.processed:
            return False
        return True

    def check_editable(self):
        '''Raise ProcessedBillError if this bill should not be edited. Call
        this before modifying a UtilBill or its child objects.
        '''
        if not self.editable():
            raise ProcessedBillError('Utility bill is not editable')

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first Charge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

    def get_supply_charges(self):
        '''Return a list of Charges that are for supply (rather than
        distribution, or other), excluding charges that are "fake" (
        has_charge == False).
        '''
        return [c for c in self.charges if c.has_charge and c.type == 'supply']

    def get_distribution_charges(self):
        '''Return a list of Charges that are for distribution (rather than
        supply, or other), excluding charges that are "fake" (
        has_charge == False).
        '''
        return [c for c in self.charges if c.has_charge and c.type == 'distribution']

    def get_total_charges(self):
        """Returns sum of all charges' totals, excluding charges that have
        errors.
        """
        return sum(charge.total for charge in self.charges
                if charge.total is not None)

    def get_supply_target_total(self):
        '''Return the sum of the 'target_total' of all supply
        charges (excluding any charge with has_charge == False).
        This is the total supply cost shown on the bill, not calculated from
        formula and rate.
        '''
        return sum(c.target_total for c in self.get_supply_charges()
                   if c.target_total is not None and c.has_charge)

    def get_total_energy_consumption(self):
        '''Return total energy consumption, i.e. value of the "REG_TOTAL"
        register, in whatever unit it uses. Return 0 if there is no
        "REG_TOTAL" (which is not supposed to happen).
        '''
        try:
            total_register = next(r for r in self.registers
                                  if r.register_binding == 'REG_TOTAL')
        except StopIteration:
            return 0
        return total_register.quantity

    def column_dict(self):
        result = dict(super(UtilBill, self).column_dict().items() +
                    [('account', self.utility_account.account),
                     ('service', 'Unknown' if self.service is None
                                           else self.service.capitalize()),
                     ('total_charges', self.target_total),
                     ('computed_total', self.get_total_charges()),
                     ('reebills', [ur.reebill.column_dict() for ur
                                   in self._utilbill_reebills]),
                     ('utility', (self.utility.column_dict() if self.utility
                                  else None)),
                     ('supplier', (self.supplier.name if
                                   self.supplier else None)),
                     ('rate_class', self.get_rate_class_name()),
                     ('state', self.state_name())])
        return result

class Register(Base):
    """A register reading on a utility bill"""

    __tablename__ = 'register'

    # allowed units for register quantities
    PHYSICAL_UNITS = [
        'BTU',
        'MMBTU',
        'kWD',
        'kWh',
        'therms',
    ]

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(Enum(*PHYSICAL_UNITS), nullable=False)
    identifier = Column(String(255), nullable=False)
    estimated = Column(Boolean, nullable=False)
    # "reg_type" field seems to be unused (though "type" values include
    # "total", "tou", "demand", and "")
    reg_type = Column(String(255), nullable=False)
    register_binding = Column(String(255), nullable=False)
    active_periods = Column(String(2048))
    meter_identifier = Column(String(255), nullable=False)

    utilbill = relationship("UtilBill", backref='registers')

    def __init__(self, utilbill, description, identifier, unit,
                estimated, reg_type, active_periods, meter_identifier,
                quantity=0.0, register_binding=''):
        """Construct a new :class:`.Register`.

        :param utilbill: The :class:`.UtilBill` on which the register appears
        :param description: A description of the register
        :param quantity: The register quantity
        :param unit: The units of the quantity (i.e. Therms/kWh)
        :param identifier: ??
        :param estimated: Boolean; whether the indicator is an estimation.
        :param reg_type:
        :param register_binding:
        :param active_periods:
        :param meter_identifier:
        """
        self.utilbill = utilbill
        self.description = description
        self.quantity = quantity
        self.unit = unit
        self.identifier = identifier
        self.estimated = estimated
        self.reg_type = reg_type
        self.register_binding = register_binding
        self.active_periods = active_periods
        self.meter_identifier = meter_identifier

    def get_active_periods(self):
        """Return a dictionary describing "active periods" of this register.
        For a time-of-use register, this dictionary should have the keys
        "active_periods_weekday" and "active_periods_weekend". A
        non-time-of-use register will have an empty dictionary.
        The value of each key is a list of (start, end) pairs of hours in [0,23]
        where the end hour is inclusive.
        """
        keys = ['active_periods_weekday', 'active_periods_weekend']
        # blank means active every hour of every day
        if self.active_periods in ('', None):
            return {key: [[0, 23]] for key in keys}
        # non-blank: parse JSON and make sure it contains all 3 keys
        result = json.loads(self.active_periods)
        assert all(key in result for key in keys)
        return result



class Charge(Base):
    """Represents a specific charge item on a utility bill.
    """
    __tablename__ = 'charge'

    # allowed units for "quantity" field of charges
    CHARGE_UNITS = Register.PHYSICAL_UNITS + ['dollars']

    # allowed values for "type" field of charges
    CHARGE_TYPES = ['supply', 'distribution']

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False)
    group = Column(String(255), nullable=False)
    quantity = Column(Float)
    unit = Column(Enum(*CHARGE_UNITS), nullable=False)
    rsi_binding = Column(String(255), nullable=False)

    quantity_formula = Column(String(1000), nullable=False)
    rate = Column(Float, nullable=False)

    # amount of the charge calculated from the quantity formula and rate
    total = Column(Float)

    # description of error in computing the quantity and/or rate formula.
    # either this or quantity and rate should be null at any given time,
    # never both or neither.
    error = Column(String(255))

    # actual charge amount shown on the bill, if known
    target_total = Column(Float)

    has_charge = Column(Boolean, nullable=False)
    shared = Column(Boolean, nullable=False)
    roundrule = Column(String(1000))
    type = Column(Enum(*CHARGE_TYPES), nullable=False)

    utilbill = relationship("UtilBill", backref=backref('charges', order_by=id))

    @staticmethod
    def is_builtin(var):
        """Checks whether the string `var` is a builtin variable or method
        :param var: the string to check being a builtin.
        """
        try:
            return eval('type(%s)' % var).__name__ == \
                   'builtin_function_or_method'
        except NameError:
            return False

    @staticmethod
    def get_variable_names(formula, filter_builtins=True):
        """Yields Python language variable names contained within the
        specified formula.
        :param formula: the Python formula parse
        :param filter_builtins: remove variables which are builtin identifiers
        """
        t = ast.parse(formula)
        var_names = (n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        if filter_builtins:
            return [var for var in var_names if not Charge.is_builtin(var)]
        return list(var_names)

    def __init__(self, utilbill, rsi_binding, rate, quantity_formula,
                 target_total=None, description='', group='', unit='',
                 has_charge=True, shared=False, roundrule="", type='supply'):
        """Construct a new :class:`.Charge`.

        :param utilbill: A :class:`.UtilBill` instance.
        :param description: A description of the charge.
        :param group: The charge group
        :param unit: The units of the quantity (i.e. Therms/kWh)
        :param rsi_binding: The rate structure item corresponding to the charge
        :param quantity_formula: The RSI quantity formula
        :param has_charge:
        :param shared:
        :param roundrule:
        """
        assert unit is not None
        self.utilbill = utilbill
        self.description = description
        self.group = group
        self.unit = unit
        self.rsi_binding = rsi_binding
        self.quantity_formula = quantity_formula
        self.target_total = target_total
        self.has_charge = has_charge
        self.shared = shared
        self.rate=rate
        self.roundrule = roundrule
        if not type in self.CHARGE_TYPES:
            raise ValueError('Invalid charge type "%s"' % type)
        self.type = type

    @classmethod
    def formulas_from_other(cls, other):
        """Constructs a charge copying the formulas and data
        from the other charge, but does not set the utilbill"""
        return cls(None,
                   other.rsi_binding,
                   other.rate,
                   other.quantity_formula,
                   description=other.description,
                   group=other.group,
                   unit=other.unit,
                   has_charge=other.has_charge,
                   shared=other.shared,
                   roundrule=other.roundrule)

    @staticmethod
    def _evaluate_formula(formula, context):
        """Evaluates the formula in the specified context
        :param formula: a `quantity_formula`
        :param context: map of binding name to `Evaluation`
        """
        if formula == '':
            return 0
        try:
            return eval(formula, {}, context)
        except SyntaxError:
            raise FormulaSyntaxError('Syntax error')
        except Exception as e:
            message = 'Error: '
            message += 'division by zero' if type(e) == ZeroDivisionError \
                else e.message
            raise FormulaError(message)

    def formula_variables(self):
        """Returns the full set of non built-in variable names referenced
         in `quantity_formula` as parsed by Python"""
        return set(Charge.get_variable_names(self.quantity_formula))

    def evaluate(self, context, update=False):
        """Evaluates the quantity and rate formulas and returns a
        `Evaluation` instance
        :param context: map of binding name to `Evaluation`
        :param update: if true, set charge attributes to formula evaluations
        :param raise_exception: Raises an exception if the charge could not be
        computed. Otherwise silently sets the error attribute of the charge
        to the exception message.
        :returns: a `Evaluation`
        """
        try:
            quantity = self._evaluate_formula(self.quantity_formula, context)
        except FormulaError as exception:
            evaluation = ChargeEvaluation(exception=exception)
        else:
            evaluation = ChargeEvaluation(quantity, self.rate)
        if update:
            self.quantity = evaluation.quantity
            self.total = evaluation.total
            self.error = None if evaluation.exception is None else \
                evaluation.exception.message
        return evaluation

    def __repr__(self):
        return '<Charge "%s">' % (self.rsi_binding)
    def get_create_utility(self, utility_name):
        session = Session()
        try:
            utility = session.query(Utility).filter_by(name=utility_name).one()
        except NoResultFound:
            utility = Utility(utility_name, Address('', '', '', '', ''))
        return utility

