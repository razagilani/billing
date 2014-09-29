'''
SQLALchemy classes for all applications that use the utility bill database.
Also contains some related classes that do not correspond to database tables.
'''
__all__ = [
    'Address',
    'Base',
    'Charge',
    'ChargeEvaluation',
    'Customer',
    'Evaluation',
    'MYSQLDB_DATETIME_MIN',
    'Register',
    'Session',
    'UtilBill',
    'UtilBillLoader',
    'check_schema_revision',
]
import ast
from datetime import datetime
import json

import sqlalchemy
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import desc
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean, \
    Enum
from sqlalchemy.ext.declarative import declarative_base
import tsort
from alembic.migration import MigrationContext

from billing.exc import NoSuchBillException, FormulaSyntaxError
from billing.exc import FormulaError
from exc import DatabaseError

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
        return all([getattr(self, x) == getattr(other, x) for x in
                    self.column_names()])

    def column_dict(self):
        '''Return dictionary of names and values for all attributes
        corresponding to database columns.
        '''
        return {c: getattr(self, c) for c in self.column_names()}
Base = declarative_base(cls=Base)


_schema_revision = '6446c51511c'
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
    """Table representing both "billing addresses" and "service addresses" in
    reebills.
    """
    __tablename__ = 'address'

    id = Column(Integer, primary_key=True)
    addressee = Column(String, nullable=False)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)

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


class Customer(Base):
    __tablename__ = 'customer'

    # this is here because there doesn't seem to be a way to get a list of
    # possible values from a SQLAlchemy.types.Enum
    SERVICE_TYPES = ('thermal', 'pv')

    id = Column(Integer, primary_key=True)
    account = Column(String, nullable=False)
    name = Column(String)
    discountrate = Column(Float(asdecimal=False), nullable=False)
    latechargerate = Column(Float(asdecimal=False), nullable=False)
    bill_email_recipient = Column(String, nullable=False)

    # null means brokerage-only customer
    service = Column(Enum(*SERVICE_TYPES))

    # "fb_" = to be assigned to the customer's first-created utility bill
    fb_utility_name = Column(String(255), nullable=False)
    fb_rate_class = Column(String(255), nullable=False)
    fb_billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False, )
    fb_service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)

    fb_billing_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='Customer.fb_billing_address_id==Address.id')
    fb_service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='Customer.fb_service_address_id==Address.id')

    def get_discount_rate(self):
        return self.discountrate

    def set_discountrate(self, value):
        self.discountrate = value

    def get_late_charge_rate(self):
        return self.latechargerate

    def set_late_charge_rate(self, value):
        self.latechargerate = value

    def __init__(self, name, account, discount_rate, late_charge_rate,
                 bill_email_recipient, fb_utility_name, fb_rate_class,
                 fb_billing_address, fb_service_address):
        """Construct a new :class:`.Customer`.
        :param name: The name of the customer.
        :param account:
        :param discount_rate:
        :param late_charge_rate:
        :param bill_email_recipient: The customer receiving email
        address for skyline-generated bills
        :fb_utility_name: The "first bill utility name" to be assigned
         as the name of the utility company on the first `UtilityBill`
         associated with this customer.
        :fb_rate_class": "first bill rate class" (see fb_utility_name)
        :fb_billing_address: (as previous)
        :fb_service address: (as previous)
        """
        self.name = name
        self.account = account
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
        self.bill_email_recipient = bill_email_recipient
        self.fb_utility_name = fb_utility_name
        self.fb_rate_class = fb_rate_class
        self.fb_billing_address = fb_billing_address
        self.fb_service_address = fb_service_address

    def __repr__(self):
        return '<Customer(name=%s, account=%s, discountrate=%s)>' \
               % (self.name, self.account, self.discountrate)


class UtilBill(Base):
    __tablename__ = 'utilbill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)

    state = Column(Integer, nullable=False)
    service = Column(String, nullable=False)
    utility = Column(String, nullable=False)
    rate_class = Column(String, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # optional, total of charges seen in PDF: user knows the bill was processed
    # correctly when the calculated total matches this number
    target_total = Column(Float)

    date_received = Column(DateTime)
    account_number = Column(String, nullable=False)

    # whether this utility bill is considered "done" by the user--mainly
    # meaning that its rate structure and charges are supposed to be accurate
    # and can be relied upon for rate structure prediction
    processed = Column(Integer, nullable=False)

    # _ids of Mongo documents
    document_id = Column(String)
    uprs_document_id = Column(String)

    customer = relationship("Customer", backref=backref('utilbills',
            order_by=id))
    billing_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.billing_address_id==Address.id')
    service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.service_address_id==Address.id')

    @property
    def bindings(self):
        """Returns all bindings across both charges and registers"""
        return set([c.rsi_binding for c in self.charges] +
                   [r.register_binding for r in self.registers])

    @staticmethod
    def validate_utilbill_period(start, end):
        '''Raises an exception if the dates 'start' and 'end' are unreasonable
        as a utility bill period: "reasonable" means start < end and (end -
        start) < 1 year.'''
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
    Complete, UtilityEstimated, Estimated, Hypothetical = range(4)

    # human-readable names for utilbill states (used in UI)
    _state_descriptions = {
        Complete: 'Final',
        UtilityEstimated: 'Utility Estimated',
        Estimated: 'Estimated',
        Hypothetical: 'Missing'
    }

    # TODO remove uprs_id, doc_id
    def __init__(self, customer, state, service, utility, rate_class,
                 billing_address, service_address, account_number='',
                 period_start=None, period_end=None, doc_id=None, uprs_id=None,
                 target_total=0, date_received=None, processed=False,
                 reebill=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.Estimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.customer = customer
        self.state = state
        self.service = service
        self.utility = utility
        self.rate_class = rate_class
        self.billing_address = billing_address
        self.service_address = service_address
        self.period_start = period_start
        self.period_end = period_end
        self.target_total = target_total
        self.date_received = date_received
        self.account_number = account_number
        self.processed = processed
        self.document_id = doc_id
        self.uprs_document_id = uprs_id

    def state_name(self):
        return self.__class__._state_descriptions[self.state]

    def __repr__(self):
        return ('<UtilBill(customer=<%s>, service=%s, period_start=%s, '
                'period_end=%s, state=%s, %s reebills)>') % (
            self.customer.account, self.service, self.period_start,
            self.period_end, self.state, len(self._utilbill_reebills))

    def is_attached(self):
        return len(self._utilbill_reebills) > 0

    def sequence_version_json(self):
        '''Returns a list of dictionaries describing reebill versions attached
        to this utility bill. Each element is of the form {"sequence":
        sequence, "version": version}. The elements are sorted by sequence and
        by version within the same sequence.
        '''
        return sorted(
            ({'sequence': ur.reebill.sequence, 'version': ur.reebill.version,
              'issue_date': ur.reebill.issue_date}
             for ur in self._utilbill_reebills),
            key=lambda element: (element['sequence'], element['version'])
        )

    def add_charge(self):
        session = Session.object_session(self)
        all_rsi_bindings = set([c.rsi_binding for c in self.charges])
        n = 1
        while ('New RSI #%s' % n) in all_rsi_bindings:
            n += 1
        charge = Charge(utilbill=self,
                        description="New Charge - Insert description here",
                        group="",
                        quantity=0.0,
                        quantity_units="",
                        rate=0.0,
                        rsi_binding="New RSI #%s" % n,
                        total=0.0)
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

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first Charge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

    def get_total_charges(self):
        """Returns sum of all charges' totals, excluding charges that have
        errors.
        """
        return sum(charge.total for charge in self.charges
                if charge.total is not None)

    def column_dict(self):
        the_dict = super(UtilBill, self).column_dict()
        reebills = [ur.reebill.column_dict() for ur in self._utilbill_reebills]
        the_dict.update({
            'account': self.customer.account,
            'service': 'Unknown' if self.service is None
                                else self.service.capitalize(),
            'total_charges': self.target_total,
            'computed_total': self.get_total_charges() if self.state <
                                UtilBill.Hypothetical else None,
            'reebills': reebills,
            'state': self.state_name()
        })
        return the_dict

class Register(Base):
    """A register reading on a utility bill"""

    __tablename__ = 'register'

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    quantity_units = Column(String(255), nullable=False)
    identifier = Column(String(255), nullable=False)
    estimated = Column(Boolean, nullable=False)
    # "reg_type" field seems to be unused (though "type" values include
    # "total", "tou", "demand", and "")
    reg_type = Column(String(255), nullable=False)
    register_binding = Column(String(255), nullable=False)
    active_periods = Column(String(2048))
    meter_identifier = Column(String(255), nullable=False)

    utilbill = relationship("UtilBill", backref='registers')

    def __init__(self, utilbill, description, quantity, quantity_units,
                 identifier, estimated, reg_type, register_binding,
                 active_periods, meter_identifier):
        """Construct a new :class:`.Register`.

        :param utilbill: The :class:`.UtilBill` on which the register appears
        :param description: A description of the register
        :param quantity: The register quantity
        :param quantity_units: The units of the quantity (i.e. Therms/kWh)
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
        self.quantity_units = quantity_units
        self.identifier = identifier
        self.estimated = estimated
        self.reg_type = reg_type
        self.register_binding = register_binding
        self.active_periods = active_periods
        self.meter_identifier = meter_identifier

    def get_active_periods(self):
        """Return a dictionary describing "active periods" of this register.
        For a time-of-use register, this dictionary should have the keys
        "active_periods_weekday", "active_periods_weekend",
        and "active_periods_holiday". For a non-time-of-use register will
        have an empty dictionary.
        """
        keys = ['active_periods_weekday', 'active_periods_weekend',
                'active_periods_holiday']
        # blank means active every hour of every day
        if self.active_periods in ('', None):
            return {key: [(0, 23)] for key in keys}
        # non-blank: parse JSON and make sure it contains all 3 keys
        result = json.loads(self.active_periods)
        assert all(key in result for key in keys)
        return result


class Charge(Base):
    """Represents a specific charge item on a utility bill.
    """

    __tablename__ = 'charge'

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False)
    group = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    quantity_units = Column(String(255), nullable=False)
    rate = Column(Float, nullable=False)
    rsi_binding = Column(String(255), nullable=False)
    total = Column(Float, nullable=False)
    error = Column(String(255))
    # description of error in computing the quantity and/or rate formula.
    # either this or quantity and rate should be null at any given time,
    # never both or neither.

    quantity_formula = Column(String(1000), nullable=False)
    has_charge = Column(Boolean, nullable=False)
    shared = Column(Boolean, nullable=False)
    roundrule = Column(String(1000))

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

    def __init__(self, utilbill, description, group, quantity, quantity_units,
                 rate, rsi_binding, total, quantity_formula="", has_charge=True,
                 shared=False, roundrule=""):
        """Construct a new :class:`.Charge`.

        :param utilbill: A :class:`.UtilBill` instance.
        :param description: A description of the charge.
        :param group: The charge group
        :param quantity: The quantity consumed
        :param quantity_units: The units of the quantity (i.e. Therms/kWh)
        :param rate: The charge per unit of quantity
        :param rsi_binding: The rate structure item corresponding to the charge
        :param total: The total charge (equal to rate * quantity)

        :param quantity_formula: The RSI quantity formula
        :param has_charge:
        :param shared:
        :param roundrule:
        """
        assert quantity_units is not None
        self.utilbill = utilbill
        self.description = description
        self.group = group
        self.quantity = quantity
        self.quantity_units = quantity_units
        self.rate = rate
        self.rsi_binding = rsi_binding
        self.total = total

        self.quantity_formula = quantity_formula
        self.has_charge = has_charge
        self.shared = shared
        self.roundrule = roundrule

    @classmethod
    def formulas_from_other(cls, other):
        """Constructs a charge copying the formulas and data
        from the other charge, but does not set the utilbill"""
        return cls(None,
                   other.description,
                   other.group,
                   other.quantity,
                   other.quantity_units,
                   other.rate,
                   other.rsi_binding,
                   other.total,
                   quantity_formula=other.quantity_formula,
                   has_charge=other.has_charge,
                   shared=other.shared,
                   roundrule=other.roundrule)

    @staticmethod
    def _evaluate_formula(formula, context):
        """Evaluates the formula in the specified context
        :param formula: a `quantity_formula`
        :param context: map of binding name to `Evaluation`
        """
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

class UtilBillLoader(object):
    '''Data access object for utility bills, used to hide database details
    from other classes so they can be more easily tested.
    '''
    def __init__(self, session):
        ''''session': SQLAlchemy session object to be used for database
        queries.
        '''
        self._session = session

    def load_real_utilbills(self, **kwargs):
        '''Returns a cursor of UtilBill objects matching the criteria given
        by **kwargs. Only "real" utility bills (i.e. UtilBill objects with
        state Estimated or lower) are included.
        '''
        cursor = self._session.query(UtilBill).filter(
                UtilBill.state <= UtilBill.Estimated)
        for key, value in kwargs.iteritems():
            cursor = cursor.filter(getattr(UtilBill, key) == value)
        return cursor

    def get_last_real_utilbill(self, account, end, service=None, utility=None,
                rate_class=None, processed=None):
        '''Returns the latest-ending non-Hypothetical UtilBill whose
        end date is before/on 'end', optionally with the given service,
        utility, rate class, and 'processed' status.
        '''
        customer = self._session.query(Customer).filter_by(account=account) \
            .one()
        cursor = self._session.query(UtilBill) \
            .filter(UtilBill.customer == customer) \
            .filter(UtilBill.state != UtilBill.Hypothetical) \
            .filter(UtilBill.period_end <= end)
        if service is not None:
            cursor = cursor.filter(UtilBill.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if processed is not None:
            assert isinstance(processed, bool)
            cursor = cursor.filter(UtilBill.processed == processed)
        result = cursor.order_by(desc(UtilBill.period_end)).first()
        if result is None:
            raise NoSuchBillException
        return result

