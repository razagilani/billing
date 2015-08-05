'''
SQLALchemy classes for all applications that use the utility bill database.
Also contains some related classes that do not correspond to database tables.
'''
from datetime import datetime
from itertools import chain
import json

import sqlalchemy
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, \
    UniqueConstraint, MetaData
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.interfaces import MapperExtension
from sqlalchemy.orm import sessionmaker, scoped_session, object_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.types import Integer, String, Float, Boolean, \
    Enum
from sqlalchemy.util.langhelpers import symbol
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect

from alembic.migration import MigrationContext

from exc import DatabaseError, \
    NoSuchBillException
from util.units import unit_registry

__all__ = ['Address', 'Base', 'AltitudeBase', 'MYSQLDB_DATETIME_MIN', 'Register', 'Session',
           'AltitudeSession', 'altitude_metadata', 'Supplier', 'SupplyGroup',
           'RateClass', 'Utility', 'UtilityAccount',
           'check_schema_revision', ]

# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900, 1, 1)

Session = scoped_session(sessionmaker())
AltitudeSession = scoped_session(sessionmaker())
altitude_metadata = MetaData()

# allowed units for register quantities.
# UnitRegistry attributes are used in the values to ensure that there's an
# entry for every one of the allowed units (otherwise unit conversion would
# fail, as it has in past bugs.)
PHYSICAL_UNITS = {
    'BTU': unit_registry.BTU,
    'MMBTU': unit_registry.MMBTU,
    'kWD': unit_registry.kWD,
    'kWh': unit_registry.kWh,
    'therms': unit_registry.therms,
}

# this type should be used for database columns whose values can be the unit
# names above
physical_unit_type = Enum(*PHYSICAL_UNITS.keys(), name='physical_unit')

GAS, ELECTRIC = 'gas', 'electric'
SERVICES = (GAS, ELECTRIC)

# this type should be used for all database columns whose values are one of
# the SERVICES above
SERVICES_TYPE = Enum(*SERVICES, name='services')


class _Base(object):
    '''Common methods for all SQLAlchemy model classes, for use both here
    and in consumers that define their own model classes.
    '''


    @classmethod
    def column_names(cls):
        """Return list of attributes names in the class that correspond to
        database columns. These are NOT necessarily the names of actual
        database columns.
        """
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

    def _get_primary_key_names(self):
        """:return: set of names of primary key columns.
        """
        return {c.key for c in class_mapper(self.__class__).primary_key}

    def clone(self):
        """Return an object identical to this one except for primary keys and
        foreign keys.
        """
        # recommended way to clone a SQLAlchemy mapped object according to
        # Michael Bayer, the author:
        # https://www.mail-archive.com/sqlalchemy@googlegroups.com/msg10895.html
        # (this code does not completely follow those instructions)
        cls = self.__class__
        foreign_key_columns = chain.from_iterable(
            c.columns for c in self.__table__.constraints if
                isinstance(c, ForeignKeyConstraint))
        foreign_keys = set(col.key for col in foreign_key_columns)

        relevant_attr_names = [x for x in self.column_names() if
                               x not in self._get_primary_key_names() and
                               x not in foreign_keys]

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

    def raw_column_dict(self, exclude=set()):
        """
        :return: dictionary whose keys are column names in the database table
        and whose values are the corresponding column values, as in the
        dictionaries it passes to the DBAPI along with the SQL format strings.
        Primary key columns are excluded if their value is None.
        SQLAlchemy probably has an easy way to get this but I couldn't find it.
        """
        mapper = self._sa_instance_state.mapper
        return {column_property.columns[0].name: getattr(self, attr_name) for
                  attr_name, column_property in mapper.column_attrs.items()
                  if column_property.columns[ 0] not in mapper.primary_key
                  and attr_name not in exclude}
                  
    def _copy_data_from(self, other):
        """Copy all column values from 'other' (except primary key),  replacing
        existing values.
        param other: object having same class as self.
        """
        assert other.__class__ == self.__class__
        # all attributes are either columns or relationships (note that some
        # relationship attributes, like charges, correspond to a foreign key
        # in a different table)
        for col_name in other.column_names():
            setattr(self, col_name, getattr(other, col_name))
        for name, property in inspect(self.__class__).relationships.items():
            other_value = getattr(other, name)
            # for a relationship attribute where this object is the parent
            # (i.e. the other object's table contains the foreign key), copy the
            # child object (or its contents, if it's a list).
            # this only goes one level into the object graph but should be OK
            # for most uses.
            # i'm sure there's a much better way to do this buried in
            # SQLAlchemy somewhere but this appears to work.
            if property.direction == symbol('ONETOMANY'):
                if isinstance(other_value, Base):
                    other_value = other_value.clone()
                elif isinstance(other_value, InstrumentedList):
                    other_value = [element.clone() for element in other_value]
            else:
                assert property.direction == symbol('MANYTOONE')
            setattr(self, name, other_value)



Base = declarative_base(cls=_Base)
AltitudeBase = declarative_base(cls=_Base)

_schema_revision = '482dddf4fe5d'


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

    # association of names of charges as displayed on bills with the
    # standardized names used in Charge.rsi_binding. this might be better
    # associated with each rate class (which defines the distribution charges)
    # and/or bill layout (which determines the display names of charges)
    charge_name_map = Column(HSTORE, nullable=False, server_default='')

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

    # for importing matrix quotes from emailed files. each is a regular
    # expression. all fields are optional but all included ones should match
    # for the email to be processed.
    matrix_email_sender = Column(String)
    matrix_email_recipient = Column(String)
    matrix_email_subject = Column(String)
    matrix_file_name = Column(String, unique=True)

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
    unit = Column(physical_unit_type, nullable=False)
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

    def get_service(self):
        return self.service


class RateClass(Base):
    """Represents a group of utility accounts that all have the same utility
    and the same pricing for distribution.

    Every bill in a rate class gets billed according to the same kinds of
    meter values (like total energy, demand, etc.) so the rate class also
    determines which _registers exist in each bill.
    determines which registers exist in each bill.

    The rate class also determines what supply contracts may be available to
    a customer.
    """
    __tablename__ = 'rate_class'
    __table_args__ = (UniqueConstraint('utility_id', 'name'),)

    GAS, ELECTRIC = 'gas', 'electric'
    SERVICES = (GAS, ELECTRIC)

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

    def get_utility(self):
        """:return: the Utility of any bill for this account, or the value of
        'fb_utility' if there are no bills.
        """
        # TODO: instead of having to do a database query when this is called,
        #  'fb_utility' should be replaced by an attribute that represents
        # the current utility.
        if len(self.utilbills) > 0:
            return self.utilbills[0].get_utility()
        return self.fb_utility

    def get_service_address(self):
        """Return the service address (Address object) of any bill for this
        account, or the value of 'fb_service_address' if there are no bills.
        """
        if len(self.utilbills) > 0:
            return self.utilbills[0].service_address
        return self.fb_service_address

    def get_last_bill(self, processed=None, end=None):
        """Return the latest-ending UtilBill belonging to this account. Only
        bills that have a 'period_end' date are included. Raise
        NoSuchBillException if this account has no bills whose end date has
        been set.

        :param processed: if True, only consider bills that are processed.
        :param end: only consider bills whose period ends on/before this date.
        :return: UtilBill
        """
        g = (u for u in self.utilbills if u.period_end is not None
             and (processed is None or u.processed)
             and (end is None
                  or (u.period_end is not None and u.period_end <= end)))
        try:
            return max(g, key=lambda utilbill: utilbill.period_end)
        except ValueError:
            raise NoSuchBillException


