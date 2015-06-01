'''
SQLALchemy classes for all applications that use the utility bill database.
Also contains some related classes that do not correspond to database tables.
'''
import ast
from datetime import date, datetime
from itertools import chain
import json

import sqlalchemy
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, \
    UniqueConstraint
from sqlalchemy.orm.interfaces import MapperExtension
from sqlalchemy.orm import sessionmaker, scoped_session, object_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean, \
    Enum
from sqlalchemy.ext.declarative import declarative_base
import tsort
from alembic.migration import MigrationContext

from exc import FormulaSyntaxError, FormulaError, DatabaseError, \
    UnEditableBillError, NotProcessable, BillingError

__all__ = ['Address', 'Base', 'Charge', 'ChargeEvaluation', 'Evaluation',
    'MYSQLDB_DATETIME_MIN', 'Register', 'Session', 'Supplier', 'SupplyGroup',
    'RateClass', 'Utility', 'UtilBill', 'UtilityAccount',
    'check_schema_revision', ]

# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900, 1, 1)

Session = scoped_session(sessionmaker())

# allowed units for register quantities
PHYSICAL_UNITS = ['BTU', 'MMBTU', 'kWD', 'kWh', 'therms', ]
physical_unit_type = Enum(*PHYSICAL_UNITS, name='physical_unit')

# types of utility service
GAS, ELECTRIC = 'gas', 'electric'
SERVICES = ('gas', 'electric')

# this type should be used for all database columns whose values are one of
# the SERVICES above
SERVICES_TYPE = Enum(*SERVICES, name='services')


class Base(object):
    '''Common methods for all SQLAlchemy model classes, for use both here
    and in consumers that define their own model classes.
    '''

    @classmethod
    def column_names(cls):
        '''Return list of attributes in the class that correspond to
        database columns.
        '''
        return [prop.key for prop in class_mapper(cls).iterate_properties if
                isinstance(prop, sqlalchemy.orm.ColumnProperty)]

    def __eq__(self, other):
        if type(self) is not type(other):
            return False
        return all([getattr(self, x) == getattr(other, x) for x in
                    self.column_names()])

    def __hash__(self):
        """Must be consistent with __eq__: if x == y, then hash(x) == hash(y)
        """
        # NOTE: do not assign non-hashable objects (such as lists) as
        # attributes!
        return hash((self.__class__.__name__,) + tuple(
            getattr(self, x) for x in self.column_names()))

    def clone(self):
        """Return an object identical to this one except for primary keys and
        foreign keys.
        """
        # recommended way to clone a SQLAlchemy mapped object according to
        # Michael Bayer, the author:
        # https://www.mail-archive.com/sqlalchemy@googlegroups.com/msg10895.html
        # (this code does not completely follow those instructions)
        cls = self.__class__
        pk_keys = set(c.key for c in class_mapper(cls).primary_key)
        foreign_key_columns = chain.from_iterable(
            c.columns for c in self.__table__.constraints if
            isinstance(c, ForeignKeyConstraint))
        foreign_keys = set(col.key for col in foreign_key_columns)

        relevant_attr_names = [x for x in self.column_names() if
                               x not in pk_keys and x not in foreign_keys]

        # NOTE it is necessary to use __new__ to avoid calling the
        # constructor here (because the constructor arguments are not known,
        # and are different for different classes).
        # MB says to create the object with __new__, but when i do that, i get
        # a "no attribute '_sa_instance_state'" AttributeError when assigning
        # the regular attributes below. creating an InstanceState like this
        # seems to fix the problem, but might not be right way.
        new_obj = cls.__new__(cls)
        class_manager = cls._sa_class_manager
        new_obj._sa_instance_state = InstanceState(new_obj, class_manager)

        # copy regular attributes from self to the new object
        for attr_name in relevant_attr_names:
            setattr(new_obj, attr_name, getattr(self, attr_name))
        return new_obj


Base = declarative_base(cls=Base)

_schema_revision = '58383ed620d3'


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
                            " Require revision %s; current revision %s" % (
                            schema_revision, current_revision))


class UtilbillCallback(MapperExtension):
    '''This class is used to update the date_modified field of UtilBill Model,
    whenever any updates are made to UtilBills.
    See http://docs.sqlalchemy.org/en/rel_0_6/orm/interfaces.html.
    '''

    def before_update(self, mapper, connection, instance):
        if object_session(instance).is_modified(instance,
                                                include_collections=False):
            instance.date_modified = datetime.utcnow()


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
            # round to nearest cent
            self.total = round(quantity * rate, 2)

        self.quantity = quantity
        self.rate = rate
        self.exception = exception


class Address(Base):
    __tablename__ = 'address'

    id = Column(Integer, primary_key=True)
    addressee = Column(String(1000), nullable=False, default='')
    street = Column(String(1000), nullable=False, default='')
    city = Column(String(1000), nullable=False, default='')
    state = Column(String(1000), nullable=False, default='')
    postal_code = Column(String(1000), nullable=False, default='')

    def __hash__(self):
        return hash(self.addressee + self.street + self.city + self.postal_code)

    def __repr__(self):
        return 'Address<(%s, %s, %s, %s, %s)' % (
        self.addressee, self.street, self.city, self.state, self.postal_code)

    def __str__(self):
        return '%s, %s, %s %s' % (
            self.street, self.city, self.state, self.postal_code)


class Utility(Base):
    '''A company that distributes energy and is responsible for the distribution
    charges on utility bills.
    '''
    __tablename__ = 'utility'

    id = Column(Integer, primary_key=True)
    address_id = Column(Integer, ForeignKey('address.id'))
    sos_supplier_id = Column(
        Integer, ForeignKey('supplier.id', ondelete='CASCADE'), unique=True, )

    name = Column(String(1000), nullable=False, unique=True)
    address = relationship("Address")
    sos_supplier = relationship('Supplier', single_parent=True,
                                cascade='all, delete-orphan')

    def __init__(self, name='', sos_supplier=None, **kwargs):
        super(Utility, self).__init__(**kwargs)
        self.name = name
        if sos_supplier is None:
            sos_supplier = Supplier(name=name + ' SOS')
        self.sos_supplier = sos_supplier

    def get_sos_supplier(self):
        return self.sos_supplier

    def __repr__(self):
        return '<Utility(%s)>' % self.name

    def __str__(self):
        return self.name

    def get_sos_supply_group(self):
        return self.sos_supply_group

class Supplier(Base):
    '''A company that supplies energy and is responsible for the supply
    charges on utility bills. This may be the same as the utility in the
    case of SOS.
    '''
    __tablename__ = 'supplier'
    id = Column(Integer, primary_key=True)
    name = Column(String(1000), nullable=False, unique=True)

    address_id = Column(Integer, ForeignKey('address.id'))
    address = relationship("Address")

    def __repr__(self):
        return '<Supplier(%s)>' % self.name

    def __str__(self):
        return self.name


class Register(Base):
    """A register reading on a utility bill"""

    __tablename__ = 'register'

    # commonly used register_binding values--there aren't any known bills
    # showing meter readings for things other than these
    TOTAL = 'REG_TOTAL'
    DEMAND = 'REG_DEMAND'
    PEAK = 'REG_PEAK'
    OFFPEAK = 'REG_OFFPEAK'
    INTERMEDIATE = 'REG_INTERMEDIATE'

    # complete set of allowed register binding values (should match the
    # definition of enum columns in the database)
    REGISTER_BINDINGS = [TOTAL, DEMAND, PEAK, INTERMEDIATE, OFFPEAK,
        'REG_TOTAL_SECONDARY', 'REG_TOTAL_TERTIARY', 'REG_POWERFACTOR',

        # related to "sub-bills": these are regular meter readings but belong
        # to a sub-period so there is more than one per bill. using special
        # register names is not a good way to implement this.
        'REG_PEAK_RATE_INCREASE', 'REG_INTERMEDIATE_RATE_INCREASE',
        'REG_OFFPEAK_RATE_INCREASE', 'FIRST_MONTH_THERMS',
        'SECOND_MONTH_THERMS',

        # related to gas supply contracts. BEGIN/END_INVENTORY might be
        # considered real meter reads, but CONTRACT_VOLUME is one of the
        # terms of the supply contract and should not be a register.
        'BEGIN_INVENTORY', 'END_INVENTORY', 'CONTRACT_VOLUME', ]
    register_binding_type = Enum(*REGISTER_BINDINGS, name='register_binding')

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False, default='')
    quantity = Column(Float, nullable=False)
    unit = Column(physical_unit_type, nullable=False)
    identifier = Column(String(255), nullable=False)
    estimated = Column(Boolean, nullable=False)
    # "reg_type" field seems to be unused (though "type" values include
    # "total", "tou", "demand", and "")
    reg_type = Column(String(255), nullable=False)
    register_binding = Column(register_binding_type, nullable=False)
    active_periods = Column(String(2048))
    meter_identifier = Column(String(255), nullable=False)

    utilbill = relationship("UtilBill",
        backref=backref('_registers', cascade='all, delete-orphan'))

    @classmethod
    def create_from_template(cls, register_template):
        """Return a new Register created based on the given RegisterTemplate.
        :param register_template: RegisterTemplate instance.
        """
        return cls(register_template.register_binding, register_template.unit,
                   description=register_template.description,
                   active_periods=register_template.active_periods)

    def __init__(self, register_binding, unit, quantity=0.0, description='',
                 identifier='', estimated=False, active_periods=None,
                 meter_identifier='', reg_type=''):
        """Construct a new :class:`.Register`.

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


class RegisterTemplate(Base):
    """Used by RateClass to determine the set of Registers in UtilBills
    belonging to each rate class. This should not be used outside of RateClass.
    """
    __tablename__ = 'register_template'

    register_template_id = Column(Integer, primary_key=True)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=False)

    register_binding = Column(Register.register_binding_type, nullable=False)
    unit = Column(Enum(*PHYSICAL_UNITS, name='physical_units'), nullable=False)
    active_periods = Column(String(2048))
    description = Column(String(255), nullable=False, default='')

    @classmethod
    def get_total_register_template(cls, unit):
        return cls(register_binding=Register.TOTAL, unit=unit)


class SupplyGroup(Base):
    """Represents a supply contract associated with one or more customers,
    or in other words a group of customers that all have the same supply
    charges. (Like rate class, but for supply instead of distribution.)

    All SOS customers with the same rate class have the same supply group,
    because the rate class also determines the supply charges.
    For non-SOS supply contracts, we usually can't find out what supply
    group a customer belongs to from their utility bill, but may be able to
    find out when switching the customer to a new supply contract.
    """
    __tablename__ = 'supply_group'
    __table_args__ = (UniqueConstraint('supplier_id', 'name'),)

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=False)
    service = Column(SERVICES_TYPE)
    name = Column(String(255), nullable=False)

    supplier = relationship('Supplier')

    def __init__(self, name='', supplier=None, service='gas'):
        assert service in SERVICES
        self.name = name
        self.supplier = supplier
        self.service = service

    def __repr__(self):
        return '<SupplyGroup(%s)>' % self.name

    def __str__(self):
        return self.name


class RateClass(Base):
    """Represents a group of utility accounts that all have the same utility
    and the same pricing for distribution.

    Every bill in a rate class gets billed according to the same kinds of
    meter values (like total energy, demand, etc.) so the rate class also
    determines which _registers exist in each bill.
    """
    __tablename__ = 'rate_class'
    __table_args__ = (UniqueConstraint('utility_id', 'name'),)

    id = Column(Integer, primary_key=True)
    utility_id = Column(Integer, ForeignKey('utility.id'), nullable=False)
    service = Column(SERVICES_TYPE, nullable=False)
    name = Column(String(255), nullable=False)
    sos_supply_group_id = Column(
        Integer, ForeignKey('supply_group.id', ondelete='CASCADE'),
        nullable=True)

    utility = relationship('Utility')
    sos_supply_group = relationship("SupplyGroup", single_parent=True,
                                    cascade='all, delete-orphan')
    register_templates = relationship('RegisterTemplate')

    def __init__(self, name='', utility=None, service='gas',
                 sos_supply_group=None):
        self.name = name
        self.utility = utility
        self.service = service
        if sos_supply_group is None:
            if utility is None:
                # the database requires utility_id to be non-null, but in tests,
                # we create RateClass instances that have no utility
                sos_supply_group = SupplyGroup(name='%s %s SOS' % ('?', name),
                    service=service)
            else:
                sos_supply_group = SupplyGroup(
                    name='%s %s SOS' % (utility.name, name),
                    supplier=utility.get_sos_supplier(), service=service)
        self.sos_supply_group = sos_supply_group

        # TODO: a newly-created rate class should have one "REG_TOTAL"
        # register by default (the unit can be picked according to
        # "service"). but for now, all UtilBills initially have no _registers
        # when they are created.
        unit = 'therms' if service == 'gas' else 'kWh'
        self.register_templates = [
            RegisterTemplate.get_total_register_template(unit)]

    def __repr__(self):
        return '<RateClass(%s)>' % self.name

    def __str__(self):
        return self.name

    def get_register_list(self):
        """Return a list of Registers for a bill belonging to this rate class.
        """
        return [Register.create_from_template(tr) for tr in
                self.register_templates]

    def get_sos_supply_group(self):
        return self.sos_supply_group



class UtilityAccount(Base):
    __tablename__ = 'utility_account'

    id = Column(Integer, primary_key=True)
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
    fb_supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=True)
    fb_supply_group_id = Column(Integer, ForeignKey('supply_group.id'),
                                nullable=True)
    fb_supply_group_id = Column(Integer, ForeignKey('supply_group.id'),
        nullable=True)

    fb_supplier = relationship('Supplier', uselist=False,
        primaryjoin='UtilityAccount.fb_supplier_id==Supplier.id')
    fb_supply_group = relationship('SupplyGroup', uselist=False,
        primaryjoin='UtilityAccount.fb_supply_group_id==SupplyGroup.id')
    fb_rate_class = relationship('RateClass', uselist=False,
        primaryjoin='UtilityAccount.fb_rate_class_id==RateClass.id')
    fb_billing_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilityAccount.fb_billing_address_id==Address.id')
    fb_service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='UtilityAccount.fb_service_address_id==Address.id')
    fb_utility = relationship('Utility')

    def __init__(self, name, account, fb_utility, fb_supplier, fb_rate_class,
                 fb_billing_address, fb_service_address, account_number='',
                 fb_supply_group=None):
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
        # if the utility is known but the supply group is not known, assume it's
        # the utility's SOS supply group
        if fb_supply_group is None and fb_rate_class is not None:
            self.fb_supply_group = self.fb_rate_class.get_sos_supply_group()
        else:
            self.fb_supply_group = fb_supply_group

    def __repr__(self):
        return '<utility_account(name=%s, account=%s)>' % (
        self.name, self.account)

    def get_service_address(self):
        """Return the service address (Address object) of any bill for this
        account, or the value of 'fb_service_address' if there are no bills.
        """
        if len(self.utilbills) > 0:
            return self.utilbills[0].service_address
        return self.fb_service_address


class Charge(Base):
    """Represents a specific charge item on a utility bill.
    """
    __tablename__ = 'charge'

    # allowed units for "quantity" field of charges
    CHARGE_UNITS = PHYSICAL_UNITS + ['dollars']
    charge_unit_type = Enum(*CHARGE_UNITS, name='charge_unit')

    # allowed values for "type" field of charges
    SUPPLY, DISTRIBUTION = 'supply', 'distribution'
    CHARGE_TYPES = [SUPPLY, DISTRIBUTION]
    charge_type_type = Enum(*CHARGE_TYPES, name='charge_type')

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)

    description = Column(String(255), nullable=False)
    quantity = Column(Float)

    unit = Column(charge_unit_type, nullable=False)
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
    type = Column(charge_type_type, nullable=False)

    @staticmethod
    def _is_builtin(var):
        """Checks whether the string `var` is a builtin variable or method
        :param var: the string to check being a builtin.
        """
        try:
            return eval(
                'type(%s)' % var).__name__ == 'builtin_function_or_method'
        except NameError:
            return False

    @staticmethod
    def _get_variable_names(formula, filter_builtins=True):
        """Yields Python language variable names contained within the
        specified formula.
        :param formula: the Python formula parse
        :param filter_builtins: remove variables which are builtin identifiers
        """
        t = ast.parse(formula)
        var_names = (n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        if filter_builtins:
            return [var for var in var_names if not Charge._is_builtin(var)]
        return list(var_names)

    @staticmethod
    def get_simple_formula(register_binding):
        """
        :param register_binding: one of the register binding values in
        Register.REGISTER_BINDINGS.
        :return: a formula for a charge that is directly proportional to the
        value of the register, such as "REG_TOTAL.quantity". Most charge
        formulas are like this.
        """
        assert register_binding in Register.REGISTER_BINDINGS
        return register_binding + '.quantity'

    def __init__(self, rsi_binding, formula='', rate=0, target_total=None,
                 description='', unit='kWh', has_charge=True, shared=False,
                 roundrule="", type=DISTRIBUTION):
        """Construct a new :class:`.Charge`.

        :param utilbill: A :class:`.UtilBill` instance.
        :param description: A description of the charge.
        :param unit: The units of the quantity (i.e. Therms/kWh)
        :param rsi_binding: The rate structure item corresponding to the charge
        :param quantity_formula: The RSI quantity formula
        :param has_charge:
        :param shared:
        :param roundrule:
        """
        assert unit is not None
        self.description = description
        self.unit = unit
        self.rsi_binding = rsi_binding
        self.quantity_formula = formula
        self.target_total = target_total
        self.has_charge = has_charge
        self.shared = shared
        self.rate = rate
        self.roundrule = roundrule
        if type not in self.CHARGE_TYPES:
            raise ValueError('Invalid charge type "%s"' % type)
        self.type = type

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

    def __repr__(self):
        return 'Charge<(%s, "%s" * %s = %s, %s)>' % (
            self.rsi_binding, self.quantity_formula, self.rate, self.total,
            self.target_total)

    def formula_variables(self):
        """Returns the full set of non built-in variable names referenced
         in `quantity_formula` as parsed by Python"""
        return set(Charge._get_variable_names(self.quantity_formula))

    def evaluate(self, context, update=False):
        """Evaluates the quantity and rate formulas and returns a
        `Evaluation` instance
        :param context: map of binding name to `Evaluation`
        :param update: if true, set charge attributes to formula evaluations
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


class UtilBill(Base):
    POLYMORPHIC_IDENTITY = 'utilbill'

    __tablename__ = 'utilbill'

    __mapper_args__ = {'extension': UtilbillCallback(),

        # single-table inheritance
        'polymorphic_identity': POLYMORPHIC_IDENTITY,
        'polymorphic_on': 'discriminator', }

    discriminator = Column(String(1000), nullable=False)

    id = Column(Integer, primary_key=True)

    utility_id = Column(Integer, ForeignKey('utility.id'), nullable=False)
    billing_address_id = Column(Integer, ForeignKey('address.id'),
                                nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
                                nullable=False)
    supplier_id = Column(Integer, ForeignKey('supplier.id'), nullable=True)
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
                                nullable=False)
    rate_class_id = Column(Integer, ForeignKey('rate_class.id'), nullable=True)
    supply_group_id = Column(Integer, ForeignKey('supply_group.id'),
                             nullable=True)
    supply_group_id = Column(Integer, ForeignKey('supply_group.id'),
        nullable=True)

    state = Column(Integer, nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    due_date = Column(Date)

    # this is created for letting bill entry user's marking/un marking a
    # bill for Time Of Use. The value of the column has nothing to do with
    # whether there are time-of-use _registers or whether the energy is
    # actually priced according to time of use
    tou = Column(Boolean, nullable=False)

    # optional, total of charges seen in PDF: user knows the bill was processed
    # correctly when the calculated total matches this number
    target_total = Column(Float)

    # date when this bill was added to the database
    date_received = Column(DateTime)

    # date when the bill was last updated in the database, initially None.
    date_modified = Column(DateTime)

    account_number = Column(String(1000), nullable=False)
    sha256_hexdigest = Column(String(64), nullable=False)

    # whether this utility bill is considered "done" by the user--mainly
    # meaning that its charges and other data are supposed to be accurate.
    processed = Column(Boolean, nullable=False)

    # date when a process was run to extract data from the bill file to fill in
    # data automatically. (note this is different from data scraped from the
    # utility web site, because that can only be done while the bill is being
    # downloaded and can't take into account information from other sources.)
    # TODO: not being used at all
    date_scraped = Column(DateTime)

    # a number seen on some bills, also known as "secondary account number". the
    # only example of it we have seen is on BGE bills where it is called
    # "Electric Choice ID" or "Gas Choice ID" (there is one for each service
    # shown on electric bills and gas bills). this is not a foreign key
    # despite the name.
    supply_choice_id = Column(String(1000))

    next_meter_read_date = Column(Date)

    # cascade for UtilityAccount relationship does NOT include "save-update"
    # to allow more control over when UtilBills get added--for example,
    # when uploading a new utility bill, the new UtilBill object should only
    # be added to the session after the file upload succeeded (because in a
    # test, there is no way to check that the UtilBill was not inserted into
    # the database because the transaction was rolled back).
    utility_account = relationship("UtilityAccount",
                                   backref=backref('utilbills', order_by=id,
                                       cascade='delete'))

    # the 'supplier' attribute should not move to UtilityAccount because
    # it can change from one bill to the next.
    supplier = relationship('Supplier', uselist=False,
                            primaryjoin='UtilBill.supplier_id==Supplier.id')
    rate_class = relationship(
        'RateClass', uselist=False,
        primaryjoin='UtilBill.rate_class_id==RateClass.id')
    supply_group = relationship(
        'SupplyGroup', uselist=False,
        primaryjoin='UtilBill.supply_group_id==SupplyGroup.id')
    billing_address = relationship(
        'Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.billing_address_id==Address.id')
    service_address = relationship(
        'Address', uselist=False, cascade='all',
        primaryjoin='UtilBill.service_address_id==Address.id')

    # the 'utility' attribute may move to UtilityAccount where it would
    # make more sense for it to be.
    utility = relationship('Utility')

    charges = relationship("Charge", backref='utilbill', order_by='Charge.id',
                           cascade='all, delete, delete-orphan')

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
    # 1. UtilityEstimated: actual utility bill whose contents were estimated by
    # the utility, and will be corrected in a later bill.
    # 2. Estimated: a bill that is estimated by us, not the utility.
    Complete, UtilityEstimated, Estimated = range(3)

    def __init__(self, utility_account, utility, rate_class, supplier=None,
                 period_start=None, period_end=None, billing_address=None,
                 service_address=None, target_total=0, date_received=None,
                 processed=False, sha256_hexdigest='', due_date=None,
                 next_meter_read_date=None, state=Complete, tou=False,
                 supply_group=None):
        """
        :param state: Complete, UtilityEstimated, or Estimated.
        """
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.utility_account = utility_account
        self.state = state
        self.utility = utility
        self.rate_class = rate_class
        self.supplier = supplier
        self.supply_group = supply_group
        if billing_address is None:
            billing_address = Address()
        self.billing_address = billing_address
        if service_address is None:
            service_address = Address()
        self.service_address = service_address
        self.period_start = period_start
        self.period_end = period_end
        self.target_total = target_total
        self.date_received = date_received
        self.processed = processed
        self.due_date = due_date
        self.account_number = utility_account.account_number
        self.next_meter_read_date = next_meter_read_date
        self.tou = tou

        # TODO: empty string as default value for sha256_hexdigest is
        # probably a bad idea. if we are writing tests that involve putting
        # UtilBills in an actual database then we should probably have actual
        # files for them.
        self.sha256_hexdigest = sha256_hexdigest

        # set _registers according to the rate class
        if rate_class is not None:
            self._registers = rate_class.get_register_list()

        self.charges = []
        self.date_modified = datetime.utcnow()

    def get_utility(self):
        return self.utility

    def get_utility_id(self):
        return self.utility_id

    def get_supplier(self):
        return self.supplier

    def get_supplier_id(self):
        return self.supplier_id

    def get_utility_name(self):
        '''Return name of this bill's utility.
        '''
        if self.utility is None:
            return None
        return self.utility.name

    def get_next_meter_read_date(self):
        '''Return date of next meter read (usually equal to the end of the next
        bill's period), or None of unknown. This may or may not be reported by
        the utility and is not necessarily accurate.
        '''
        return self.next_meter_read_date

    def set_next_meter_read_date(self, next_meter_read_date):
        assert isinstance(next_meter_read_date, date)
        self.next_meter_read_date = next_meter_read_date

    def get_rate_class_name(self):
        '''Return name of this bill's rate class or None if the rate class is
        None (unknown).
        '''
        if self.rate_class is None:
            return None
        return self.rate_class.name

    def get_supply_group_name(self):
        """Return name of this bill's supply_group or None if the supply_group
        is None (unknown).
        """
        if self.supply_group is None:
            return None
        return self.supply_group.name

    def get_supply_group(self):
        return self.supply_group

    def set_supply_group(self, supply_group):
        """Set the supply_group
        """
        self.supply_group = supply_group

    def get_rate_class(self):
        return self.rate_class

    def get_rate_class_id(self):
        return self.rate_class_id

    def set_utility(self, utility):
        """Set the utility, and set the rate class to None if the utility is
        different from the current one.
        :param utility: Utility or None
        """
        if utility != self.utility:
            self.set_rate_class(None)
        self.utility = utility

    def set_rate_class(self, rate_class):
        """Set the rate class and also update the set of _registers to match
        the new rate class (no _registers of rate_class is None).
        :param rate_class: RateClass or None
        """
        if rate_class is None:
            self._registers = []
        else:
            self._registers = rate_class.get_register_list()
        self.rate_class = rate_class

    def get_supplier_name(self):
        '''Return name of this bill's supplier or None if the supplier is
        None (unknown).
        '''
        if self.supplier is None:
            return None
        return self.supplier.name

    def get_utility_account_number(self):
        return self.utility_account.account_number

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
                   self.utility_account.account, self.get_service(),
                   self.period_start, self.period_end, self.state)

    def add_charge(self, **charge_kwargs):
        self.check_editable()
        session = Session.object_session(self)
        all_rsi_bindings = set([c.rsi_binding for c in self.charges])
        n = 1
        while ('New Charge %s' % n) in all_rsi_bindings:
            n += 1
        charge = Charge(
            rsi_binding=charge_kwargs.get('rsi_binding', "New Charge %s" % n),
            rate=charge_kwargs.get('rate', 0.0),
            formula=charge_kwargs.get('quantity_formula', ''),
            description=charge_kwargs.get('description',
                "New Charge - Insert description here"),
            unit=charge_kwargs.get('unit', "dollars"),
            type=charge_kwargs.get('type', Charge.DISTRIBUTION))
        self.charges.append(charge)
        session.add(charge)
        registers = self._registers
        charge.quantity_formula = '' if len(registers) == 0 else \
            '%s.quantity' % Register.TOTAL if any(
                [register.register_binding == Register.TOTAL for register in
                 registers]) else \
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
                # binding depends on depended_binding
                dependency_graph.append((depended_binding, binding))
                independent_bindings.discard(binding)
                independent_bindings.discard(depended_binding)

        while True:
            try:
                sortresult = tsort.topological_sort(dependency_graph)
            except tsort.GraphError as g:
                circular_bindings = set(g.args[1])
                independent_bindings.update(circular_bindings)
                dependency_graph = [(a, b) for a, b in dependency_graph if
                                    b not in circular_bindings]
            except KeyError as e:
                # tsort sometimes gets a KeyError when generating its error
                # message about a cycle. in that case there's only one
                # binding to move into 'independent bindings'
                binding = e.args[0]
                independent_bindings.add(binding)
                dependency_graph = [(a, b) for a, b in dependency_graph if
                                    b != binding]
            else:
                break
        order = list(independent_bindings) + [x for x in sortresult if
                                              x not in independent_bindings]
        return sorted(self.charges, key=lambda x: order.index(x.rsi_binding))

    def compute_charges(self, raise_exception=False):
        """Computes and updates the quantity, rate, and total attributes of
        all charges associated with `UtilBill`.
        :param raise_exception: Raises an exception if any charge could not be
        computed. Otherwise silently sets the error attribute of the charge
        to the exception message.
        """
        self.check_editable()
        context = {r.register_binding: Evaluation(r.quantity) for r in
                   self._registers}
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

    def regenerate_charges(self, pricing_model):
        """Replace this bill's charges with new ones generated by
        'pricing_model'.
        """
        self.check_editable()
        self.charges = pricing_model.get_predicted_charges(self)
        self.compute_charges()

    def set_processed(self, value):
        """Make this bill "processed" or not.
        :param value: boolean
        """
        assert isinstance(value, bool)
        if value:
            self.check_processable()
        self.processed = value

    def is_processable(self):
        '''Returns False if a bill is missing any of the required fields
        '''
        return None not in (
        self.utility, self.rate_class, self.supplier, self.period_start,
        self.period_end)

    def check_processable(self):
        '''Raises NotProcessable if this bill cannot be marked as processed.'''
        if not self.is_processable():
            attrs = ['utility', 'rate_class', 'supplier', 'period_start',
                     'period_end']
            missing_attrs = ', '.join(
                [attr for attr in attrs if getattr(self, attr) is None])
            raise NotProcessable("The following fields have to be entered "
                                 "before this utility bill can be marked as "
                                 "processed: " + missing_attrs)

    def editable(self):
        if self.processed:
            return False
        return True

    def check_editable(self):
        '''Raise ProcessedBillError if this bill should not be edited. Call
        this before modifying a UtilBill or its child objects.
        '''
        if not self.editable():
            raise UnEditableBillError('Utility bill is not editable')

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
        return [c for c in self.charges if
                c.has_charge and c.type == 'distribution']

    def get_total_charges(self):
        """Returns sum of all charges' totals, excluding charges that have
        errors.
        """
        return sum(
            charge.total for charge in self.charges if charge.total is not None)

    def get_total_energy(self):
        # NOTE: this may have been implemented already on another branch;
        # remove duplicate when merged
        try:
            total_register = next(r for r in self._registers if
                                  r.register_binding == Register.TOTAL)
        except StopIteration:
            return 0
        return total_register.quantity

    def set_total_energy(self, quantity):
        self.check_editable()
        total_register = next(
            r for r in self._registers if r.register_binding == Register.TOTAL)
        total_register.quantity = quantity

    def get_register_by_binding(self, register_binding):
        """Return the register whose register_binding is 'register_binding'.
        This should only be called by consumers that need to know about
        _registers--not to get total energy, demand, etc. (Maybe there
        shouldn't be any consumers that know about _registers, but currently
        reebill.fetch_bill_data.RenewableEnergyGetter does.)
        :param register_binding: register binding string
        """
        try:
            register = next(r for r in self._registers if
                            r.register_binding == register_binding)
        except StopIteration:
            raise BillingError('No register "%s"' % register_binding)
        return register

    def get_supply_target_total(self):
        '''Return the sum of the 'target_total' of all supply
        charges (excluding any charge with has_charge == False).
        This is the total supply cost shown on the bill, not calculated from
        formula and rate.
        '''
        return sum(c.target_total for c in self.get_supply_charges() if
                   c.target_total is not None and c.has_charge)

    def set_total_meter_identifier(self, meter_identifier):
        '''sets the value of meter_identifier field of the register with
        register_binding of REG_TOTAL'''
        # TODO: make this more generic once implementation of Regiter is changed
        self.check_editable()
        register = next(
            r for r in self._registers if r.register_binding == Register.TOTAL)
        register.meter_identifier = meter_identifier

    def get_total_meter_identifier(self):
        '''returns the value of meter_identifier field of the register with
        register_binding of REG_TOTAL.'''
        try:
            register = next(r for r in self._registers if
                            r.register_binding == Register.TOTAL)
        except StopIteration:
            return None
        return register.meter_identifier

    def get_total_energy_consumption(self):
        '''Return total energy consumption, i.e. value of the total
        register, in whatever unit it uses. Return 0 if there is no
        total register (which is not supposed to happen).
        '''
        try:
            total_register = next(r for r in self._registers if
                                  r.register_binding == Register.TOTAL)
        except StopIteration:
            return 0
        return total_register.quantity

    def get_service(self):
        if self.rate_class is not None:
            return self.rate_class.service
        return None
