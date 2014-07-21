"""
Utility functions to interact with state database
"""
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta, datetime, date
from itertools import groupby, chain
from operator import attrgetter, itemgetter
import logging

import sqlalchemy
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.base import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from sqlalchemy.sql.expression import desc, asc
from sqlalchemy import func
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean
from sqlalchemy.ext.associationproxy import association_proxy
import tsort
from alembic.migration import MigrationContext

from billing.processing.exceptions import IssuedBillError, NoSuchBillException,\
        RegisterError, FormulaSyntaxError

from billing.processing.exceptions import NoRSIError, FormulaError, RSIError
from exc import DatabaseError



# Python's datetime.min is too early for the MySQLdb module; including it in a
# query to mean "the beginning of time" causes a strptime failure, so this
# value should be used instead.
MYSQLDB_DATETIME_MIN = datetime(1900,1,1)

log = logging.getLogger(__name__)

Session = scoped_session(sessionmaker())

class Base(object):

    @classmethod
    def column_names(cls):
        return [prop.key for prop in class_mapper(cls).iterate_properties
                if isinstance(prop, sqlalchemy.orm.ColumnProperty)]

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base(cls=Base)


_schema_revision = '4f2f8e2f7cd'

def check_schema_revision(schema_revision=_schema_revision):
    """Checks to see whether the database schema revision matches the 
    revision expected by the model metadata.
    """
    s = Session()
    conn = s.connection()
    context = MigrationContext.configure(conn)
    current_revision = context.get_current_revision()
    if current_revision != schema_revision:
        raise DatabaseError("Database schema revision mismatch."
                            " Require revision %s; current revision %s"
                            % (schema_revision, current_revision))
    log.debug('Verified database at schema revision %s' % current_revision)

class Address(Base):
    '''Table representing both "billing addresses" and "service addresses" in
    reebills.
    '''
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

    def __hash__(self):
        return hash(self.addressee + self.street + self.city +
                    self.postal_code)

    def __eq__(self, other):
        return all([
            self.addressee == other.addressee,
            self.street == other.street,
            self.city == other.city,
            self.state == other.state,
            self.postal_code == other.postal_code
        ])

    def __repr__(self):
        return 'Address<(%s, %s, %s)' % (self.addressee, self.street,
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
            'postalcode': self.postal_code,
        }


class Customer(Base):
    __tablename__ = 'customer'

    id = Column(Integer, primary_key=True)
    account = Column(String, nullable=False)
    name = Column(String)
    discountrate = Column(Float(asdecimal=False), nullable=False)
    latechargerate = Column(Float(asdecimal=False), nullable=False)
    # this can be null for existing accounts because accounts only use the
    # template document for their first-ever utility bill
    utilbill_template_id = Column(String)

    # email address(es) to receive reebills
    bill_email_recipient = Column(String, nullable=False)

    def get_discount_rate(self):
        return self.discountrate
    def set_discountrate(self, value):
        self.discountrate = value
    def get_late_charge_rate(self):
        return self.latechargerate
    def set_late_charge_rate(self, value):
        self.latechargerate = value

    def __init__(self, name, account, discount_rate, late_charge_rate,
            utilbill_template_id, bill_email_recipient):
        self.name = name
        self.account = account
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
        self.utilbill_template_id = utilbill_template_id
        self.bill_email_recipient = bill_email_recipient

    def __repr__(self):
        return '<Customer(name=%s, account=%s, discountrate=%s)>' \
                % (self.name, self.account, self.discountrate)


class ReeBill(Base):
    __tablename__ = 'reebill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    sequence = Column(Integer, nullable=False)
    issued = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    issue_date = Column(Date)

    # new fields from Mongo
    ree_charge = Column(Float, nullable=False)
    balance_due = Column(Float, nullable=False)
    balance_forward = Column(Float, nullable=False)
    discount_rate = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    late_charge_rate = Column(Float, nullable=False)
    late_charge = Column(Float, nullable=False)
    total_adjustment = Column(Float, nullable=False)
    manual_adjustment = Column(Float, nullable=False)
    payment_received = Column(Float, nullable=False)
    prior_balance = Column(Float, nullable=False)
    ree_value = Column(Float, nullable=False)
    ree_savings = Column(Float, nullable=False)
    email_recipient = Column(String, nullable=True)
    processed = Column(Boolean, default=False)

    billing_address_id = Column(Integer, ForeignKey('address.id'),
                                nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
                                nullable=False)

    customer = relationship("Customer", backref=backref('reebills',
            order_by=id))

    # "primaryjoin is necessary because ReeBill has two foreign keys to Address
    billing_address = relationship('Address', uselist=False, cascade='all',
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
    # # scope; there is no instance of UtilBill or ReeBill at the time this
    # code is executed. it also does not work to move the code into __init__
    # and assign the 'utilbills' attribute to a particular ReeBill instance
    # or vice versa. there may be a way to make SQLAlchemy do this (maybe by
    # switching to "classical" class-definition style?) but i decided it was
    # sufficient to have only a one-directional relationship from ReeBill to
    # UtilBill.
    # documentation:
    # http://docs.sqlalchemy.org/en/rel_0_8/orm/extensions/associationproxy.html
    # AssociationProxy code:
    # https://github.com/zzzeek/sqlalchemy/blob/master/lib/sqlalchemy/ext/associationproxy.py
    # example code (showing only one-directional relationship):
    # https://github.com/zzzeek/sqlalchemy/blob/master/examples/association/proxied_association.py
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

    def get_period(self):
        '''Returns period of the first (only) utility bill for this reebill
        as tuple of dates.
        '''
        assert len(self.utilbills) == 1
        return self.utilbills[0].period_start, self.utilbills[0].period_end

    def update_readings_from_document(self, utilbill_doc):
        '''Updates the set of Readings associated with this ReeBill to match
        the list of registers in the given utility bill document. Renewable
        energy quantities are all set to 0.
        '''
        session = Session.object_session(self)
        for r in self.readings:
            session.delete(r)
        self.readings = [Reading(reg_dict['register_binding'], 'Energy Sold',
                reg_dict['quantity'], 0, '', reg_dict['quantity_units'])
                for reg_dict in chain.from_iterable(
                (r for r in m['registers']) for m in utilbill_doc['meters'])]
        return None

    def update_readings_from_reebill(self, reebill_readings, utilbill_doc):
        '''Updates the set of Readings associated with this ReeBill to match
        the list of registers in the given reebill_readings. Readings that do not
        have a register binding that matches a register in 'utilbill_doc' are
        ignored.
        '''
        session = Session.object_session(self)
        for r in self.readings:
            session.delete(r)
        utilbill_register_bindings = {r['register_binding']
                for r in chain.from_iterable(m['registers']
                for m in utilbill_doc['meters'])}
        self.readings = [Reading(r.register_binding, r.measure, 0,
                0, r.aggregate_function, r.unit) for r in reebill_readings
                if r.register_binding in utilbill_register_bindings]

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
            elif unit =='kwd':
                total_therms += quantity
            else:
                raise ValueError('Unknown energy unit: "%s"' % unit)

        return total_therms

    def update_readings_from_reebill(self, reebill_readings, utilbill_doc):
        '''Updates the set of Readings associated with this ReeBill to match
        the list of registers in the given reebill_readings. Readings that do not
        have a register binding that matches a register in 'utilbill_doc' are
        ignored.
        '''
        session = Session.object_session(self)
        for r in self.readings:
            session.delete(r)
        utilbill_register_bindings = {r['register_binding']
                for r in chain.from_iterable(m['registers']
                for m in utilbill_doc['meters'])}
        self.readings = [Reading(r.register_binding, r.measure, 0,
                0, r.aggregate_function, r.unit) for r in reebill_readings
                if r.register_binding in utilbill_register_bindings]

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
            elif unit =='kwd':
                total_therms += quantity
            else:
                raise ValueError('Unknown energy unit: "%s"' % unit)

        return total_therms

    def compute_charges(self, uprs, reebill_dao):
        """Updates `quantity`, `rate`, and `total` attributes all charges in
        the :class:`.Reebill` according to the formulas in the RSIs in the
        given rate structures.
        :param uprs: A uprs from MongoDB
        :parm reebill_dao:
        """
        session = Session.object_session(self)
        for charge in self.charges:
            session.delete(charge)
        self.charges = []

        uprs.validate()
        rate_structure = uprs
        rsis = rate_structure.rates

        utilbill = self.utilbill

        # raise exception if any utility bill charges could not be computed; it
        # doesn't make sense to base a reebill on a broken utility bill
        utilbill_doc = reebill_dao.load_doc_for_utilbill(utilbill)
        utilbill.compute_charges(uprs, utilbill_doc, raise_exception=True)

        #[MN]:This code temporary until utilbill_doc stops storing register data
        # We duplicate the utilbill and update its register quantities,
        # assigning them to the register readings from self.readings. Then, we
        # run though the charge calculation logic for the duplicate utilbill,
        # and then we copy back the charges onto the reebill
        hypothetical_utilbill = deepcopy(utilbill_doc)
        hypothetical_registers = chain.from_iterable(m['registers'] for m
                 in hypothetical_utilbill['meters'])
        for reading in self.readings:
            h_register = next(r for r in hypothetical_registers if r[
                    'register_binding'] == reading.register_binding)
            h_register['quantity'] = reading.hypothetical_quantity


        rsi_bindings = set(rsi['rsi_binding'] for rsi in uprs.rates)
        for c in (x for x in self.charges if x.rsi_binding not in rsi_bindings):
            raise NoRSIError('No rate structure item for "%s"' % c)

        # identifiers in RSI formulas are of the form "NAME.{quantity,rate,total}"
        # (where NAME can be a register or the RSI_BINDING of some other charge).
        # these are not valid python identifiers, so they can't be parsed as
        # individual names. this dictionary maps names to "quantity"/"rate"/"total"
        # to float values; RateStructureItem.compute_charge uses it to get values
        # for the identifiers in the RSI formulas. it is initially filled only with
        # register names, and the inner dictionary corresponding to each register
        # name contains only "quantity".
        identifiers = defaultdict(lambda:{})
        for meter in hypothetical_utilbill['meters']:
            for register in meter['registers']:
                identifiers[register['register_binding']]['quantity'] = \
                        register['quantity']

        # get dictionary mapping rsi_bindings names to the indices of the
        # corresponding RSIs in an alphabetical list. 'rsi_numbers' assigns a number
        # to each.
        rsi_numbers = {rsi.rsi_binding: index for index, rsi in enumerate(rsis)}

        # the dependencies of some RSIs' formulas on other RSIs form a
        # DAG, which will be represented as a list of pairs of RSI numbers in
        # 'rsi_numbers'. this list will be used to determine the order
        # in which charges get computed. to build the list, find all identifiers
        # in each RSI formula that is not a register name; every such identifier
        # must be the name of an RSI, and its presence means the RSI whose
        # formula contains that identifier depends on the RSI whose rsi_binding is
        # the identifier.
        dependency_graph = []
        # the list 'independent_rsi_numbers' initially contains all RSI
        # numbers, and by the end of the loop will contain only the numbers of
        # RSIs that have no relationship to another one
        independent_rsi_numbers = set(rsi_numbers.itervalues())

        for rsi in rsis:
            this_rsi_num = rsi_numbers[rsi.rsi_binding]

            # for every node in the AST of the RSI's "quantity" and "rate"
            # formulas, if the 'ast' module labels that node as an
            # identifier, and its name does not occur in 'identifiers' above
            # (which contains only register names), add the tuple (this
            # charge's number, that charge's number) to 'dependency_graph'.
            for identifier in rsi.get_identifiers():
                if identifier in identifiers:
                    continue
                try:
                    other_rsi_num = rsi_numbers[identifier]
                except KeyError:
                    # TODO might want to validate identifiers before computing
                    # for clarity
                    raise FormulaError(('Unknown variable in formula of RSI '
                            '"%s": %s') % (rsi.rsi_binding, identifier))
                # a pair (x,y) means x precedes y, i.e. y depends on x
                dependency_graph.append((other_rsi_num, this_rsi_num))
                independent_rsi_numbers.discard(other_rsi_num)
                independent_rsi_numbers.discard(this_rsi_num)

        # charges that don't depend on other charges can be evaluated before ones
        # that do.
        evaluation_order = list(independent_rsi_numbers)

        # 'evaluation_order' now contains only the indices of charges that don't
        # have dependencies. topological sort the dependency graph to find an
        # evaluation order that works for the charges that do have dependencies.
        try:
            evaluation_order.extend(tsort.topological_sort(dependency_graph))
        except tsort.GraphError as g:
            # if the graph contains a cycle, provide a more comprehensible error
            # message with the charge numbers converted back to names
            names_in_cycle = ', '.join(all_rsis[i]['rsi_binding'] for i in
                    g.args[1])
            raise RSIError('Circular dependency: %s' % names_in_cycle)

        assert len(evaluation_order) == len(rsis)

        all_charges = {charge.rsi_binding: charge for charge in self.charges}

        assert len(evaluation_order) == len(rsis)
        acs = {charge.rsi_binding: charge for charge in utilbill.charges}
        for rsi_number in evaluation_order:
            rsi = rsis[rsi_number]
            quantity, rate, error = rsi.compute_charge(identifiers)
            total = quantity * rate
            ac = acs[rsi.rsi_binding]
            quantity_units = ac.quantity_units \
                    if ac.quantity_units is not None else ''
            self.charges.append(ReeBillCharge(self, rsi.rsi_binding,
                    ac.description, ac.group, ac.quantity,
                    quantity, quantity_units, ac.rate, rate, ac.total,
                    total))
            identifiers[rsi.rsi_binding]['quantity'] = quantity
            identifiers[rsi.rsi_binding]['rate'] = rate
            identifiers[rsi.rsi_binding]['total'] = total


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
        assert len(self.utilbills) == 1
        return sum(charge.a_total for charge in self.charges)

    def get_total_hypothetical_charges(self):
        '''Returns sum of "hypothetical" versions of all charges.
        '''
        assert len(self.utilbills) == 1
        return sum(charge.h_total for charge in self.charges)

    def get_service_address_formatted(self):
        return str(self.service_address)

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first ReeBillCharge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

class UtilbillReebill(Base):
    '''Class corresponding to the "utilbill_reebill" table which represents the
    many-to-many relationship between "utilbill" and "reebill".''' 
    __tablename__ = 'utilbill_reebill'

    reebill_id = Column(Integer, ForeignKey('reebill.id'), primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), primary_key=True)
    document_id = Column(String)
    uprs_document_id = Column(String)

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
    rsi_binding = Column(String, nullable=False)
    description = Column(String, nullable=False)

    # NOTE alternate name is required because you can't have a column called
    # "group" in MySQL
    group = Column(String, name='group_name', nullable=False)

    a_quantity = Column(Float, nullable=False)
    h_quantity = Column(Float, nullable=False)
    quantity_unit = Column(String, nullable=False)
    a_rate = Column(Float, nullable=False)
    h_rate = Column(Float, nullable=False)
    a_total = Column(Float, nullable=False)
    h_total = Column(Float, nullable=False)

    def __init__(self, reebill, rsi_binding, description, group, a_quantity,
                h_quantity, quantity_unit, a_rate, h_rate,
                a_total, h_total):
        self.reebill_id = reebill.id
        self.rsi_binding = rsi_binding
        self.description = description
        self.group = group
        self.a_quantity, self.h_quantity = a_quantity, h_quantity
        self.quantity_unit = quantity_unit
        self.a_rate, self.h_rate = a_rate, h_rate
        self.a_total, self.h_total = a_total, h_total

class Reading(Base):
    '''Stores utility register readings and renewable energy offsetting the
    value of each register.
    '''
    __tablename__ = 'reading'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id'))

    # identifies which utility bill register this corresponds to
    register_binding = Column(String, nullable=False)

    # name of measure in OLAP database to use for getting renewable energy
    # quantity
    measure = Column(String, nullable=False)

    # actual reading from utility bill
    conventional_quantity = Column(Float, nullable=False)

    # renewable energy offsetting the above
    renewable_quantity = Column(Float, nullable=False)

    aggregate_function = Column(String, nullable=False)

    unit = Column(String, nullable=False)

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
        return hash(self.register_binding + self.measure + str(self.conventional_quantity) +
                    str(self.renewable_quantity) + self.aggregate_function + self.unit)

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

class UtilBill(Base):
    __tablename__ = 'utilbill'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    state = Column(Integer, nullable=False)
    service = Column(String, nullable=False)
    utility = Column(String, nullable=False)
    rate_class = Column(String, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_charges = Column(Float)
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

    @classmethod
    def validate_utilbill_period(self, start, end):
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
    # 2. Skyline estimated: a bill that is known to exist (and whose dates are
    # correct) but whose contents were estimated by Skyline.
    # 3. Hypothetical: Skyline supposes that there is probably a bill during a
    # certain time period and estimates what its contents would be if it
    # existed. Such a bill may not really exist (since we can't even know how
    # many bills there are in a given period of time), and if it does exist,
    # its actual dates will probably be different than the guessed ones.
    # TODO 38385969: not sure this strategy is a good idea
    Complete, UtilityEstimated, SkylineEstimated, Hypothetical = range(4)

    # human-readable names for utilbill states (used in UI)
    _state_descriptions = {
        Complete: 'Final',
        UtilityEstimated: 'Utility Estimated',
        SkylineEstimated: 'Skyline Estimated',
        Hypothetical: 'Missing'
    }

    def __init__(self, customer, state, service, utility, rate_class,
            account_number='', period_start=None, period_end=None, doc_id=None,
            uprs_id=None, total_charges=0, date_received=None,  processed=False,
            reebill=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.SkylineEstimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.customer = customer
        self.state = state
        self.service = service
        self.utility = utility
        self.rate_class = rate_class
        self.period_start = period_start
        self.period_end = period_end
        self.total_charges = total_charges
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
              'issue_date':ur.reebill.issue_date}
                 for ur in self._utilbill_reebills),
            key=lambda element: (element['sequence'], element['version'])
        )

    # TODO: this is no longer used; client receives JSON and renders it as a
    # string
    def sequence_version_string(self):
        '''Returns a string describing sequences and versions of reebills
        attached to this utility bill, consisting of sequences followed by a
        comma-separated list of versions of that sequence, e.g. "1-0,1,2, 2-0".
        '''
        # group _utilbill_reebills by sequence, sorted by version within each
        # group
        groups = groupby(sorted(self._utilbill_reebills,
                key=lambda x: (x.reebill.sequence, x.reebill.version)),
                key=attrgetter('reebill.sequence'))
        return ', '.join('%s-%s' % (sequence,
                ','.join(str(ur.reebill.version) for ur in group))
                for (sequence, group) in groups)

    def refresh_charges(self, rates):
        """Replaces the `charges` list on the :class:`.UtilityBill` based
        on the specified rates.
        :param rates: A list of UPRS.rates objects
        """
        session = Session.object_session(self)
        for charge in self.charges:
            assert Session.object_session(charge) is session
            # TODO: charge disappears from session here, but not from
            # self.charges.
            session.delete(charge)
            session.flush()
        # inserting this line makes the the test pass, but why is it necessary?
        #self.charges = []

        for rsi in sorted(rates, key=attrgetter('rsi_binding')):
            session.add(Charge(utilbill=self,
                               description=rsi.description,
                               group=rsi.group,
                               quantity=0,
                               quantity_units=rsi.quantity_units,
                               rate=0,
                               rsi_binding=rsi.rsi_binding,
                               total=0))

    def compute_charges(self, uprs, utilbill_doc, raise_exception=False):
        """Updates `quantity`, `rate`, and `total` attributes all charges in
        the :class:`.UtilityBill` according to the formulas in the RSIs in the
        given rate structures.
        :param uprs: A uprs from MongoDB
        :param utillbill_doc: The utilbill_doc from mongodb. Needed for meters
        :param raise_exception: if True, raises an RSIError if any charge could
        not be computed.
        """
        uprs.validate()
        rate_structure = uprs
        rsis = rate_structure.rates

        rsi_bindings = set(rsi['rsi_binding'] for rsi in uprs.rates)
        for c in (x for x in self.charges if x.rsi_binding not in rsi_bindings):
            raise NoRSIError('No rate structure item for "%s"' % c)

        # This code temporary until utilbill_doc stops holding RSIs
        # identifiers in RSI formulas are of the form "NAME.{quantity,rate,total}"
        # (where NAME can be a register or the RSI_BINDING of some other charge).
        # these are not valid python identifiers, so they can't be parsed as
        # individual names. this dictionary maps names to "quantity"/"rate"/"total"
        # to float values; RateStructureItem.compute_charge uses it to get values
        # for the identifiers in the RSI formulas. it is initially filled only with
        # register names, and the inner dictionary corresponding to each register
        # name contains only "quantity".
        identifiers = defaultdict(lambda:{})
        for meter in utilbill_doc['meters']:
            for register in meter['registers']:
                identifiers[register['register_binding']]['quantity'] = \
                        register['quantity']

        # get dictionary mapping rsi_bindings names to the indices of the
        # corresponding RSIs in an alphabetical list. 'rsi_numbers' assigns a number
        # to each.
        rsi_numbers = {rsi.rsi_binding: index for index, rsi in enumerate(rsis)}

        # the dependencies of some RSIs' formulas on other RSIs form a
        # DAG, which will be represented as a list of pairs of RSI numbers in
        # 'rsi_numbers'. this list will be used to determine the order
        # in which charges get computed. to build the list, find all identifiers
        # in each RSI formula that is not a register name; every such identifier
        # must be the name of an RSI, and its presence means the RSI whose
        # formula contains that identifier depends on the RSI whose rsi_binding is
        # the identifier.
        dependency_graph = []
        # the list 'independent_rsi_numbers' initially contains all RSI
        # numbers, and by the end of the loop will contain only the numbers of
        # RSIs that have no relationship to another one
        independent_rsi_numbers = set(rsi_numbers.itervalues())

        for rsi in rsis:
            this_rsi_num = rsi_numbers[rsi.rsi_binding]

            # for every node in the AST of the RSI's "quantity" and "rate"
            # formulas, if the 'ast' module labels that node as an
            # identifier, and its name does not occur in 'identifiers' above
            # (which contains only register names), add the tuple (this
            # charge's number, that charge's number) to 'dependency_graph'.
            try:
                this_rsi_identifiers = list(rsi.get_identifiers())
            except FormulaSyntaxError:
                # if this RSI has a syntax error, its number will remain in
                # 'independent_rsi_numbers' because it's independent of others
                pass
            else:
                for identifier in this_rsi_identifiers:
                    if identifier in identifiers:
                        continue
                    try:
                        other_rsi_num = rsi_numbers[identifier]
                    except KeyError:
                        # unknown variable in RSI formula: leave the RSI in
                        # 'independent_rsi_numbers'
                        continue
                    # a pair (x,y) means x precedes y, i.e. y depends on x
                    dependency_graph.append((other_rsi_num, this_rsi_num))
                    independent_rsi_numbers.discard(other_rsi_num)
                    independent_rsi_numbers.discard(this_rsi_num)

        # charges that don't depend on other charges can be evaluated before ones
        # that do.
        evaluation_order = list(independent_rsi_numbers)

        # 'evaluation_order' now contains only the indices of charges that don't
        # have dependencies. topological sort the dependency graph to find an
        # evaluation order that works for the charges that do have dependencies.
        try:
            evaluation_order.extend(tsort.topological_sort(dependency_graph))
        except tsort.GraphError as g:
            # if the graph contains a cycle, provide a more comprehensible error
            # message with the charge numbers converted back to names
            names_in_cycle = ', '.join(all_rsis[i]['rsi_binding'] for i in
                    g.args[1])
            raise RSIError('Circular dependency: %s' % names_in_cycle)

        assert len(evaluation_order) == len(rsis)

        all_charges = {charge.rsi_binding: charge for charge in self.charges}

        assert len(evaluation_order) == len(rsis)

        for rsi_number in evaluation_order:
            rsi = rsis[rsi_number]
            quantity, rate, error = rsi.compute_charge(identifiers)
            if raise_exception and error is not None:
                raise error
            total = quantity * rate if error is None else None
            try:
                charge = all_charges[rsi.rsi_binding]
            except KeyError:
                pass
            else:
                charge.description = rsi['description']
                charge.quantity = quantity
                charge.rate = rate
                charge.total = total
                charge.error = None if error is None else error.message

            # quantity/rate/total of this charge can only be used as identifiers
            # in other charges if there was no error
            if error is None:
                identifiers[rsi.rsi_binding]['quantity'] = quantity
                identifiers[rsi.rsi_binding]['rate'] = rate
                identifiers[rsi.rsi_binding]['total'] = total

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first Charge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

    def total_charge(self):
        return sum(charge.total for charge in self.charges)

class Charge(Base):
    """Represents a specific charge item on a utility bill.
    """
    __tablename__ = 'charge'

    id = Column(Integer, primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)
    description = Column(String(255))
    group = Column(String(255))
    quantity = Column(Float)
    quantity_units = Column(String(255))
    rate = Column(Float)
    rsi_binding = Column(String(255))
    total = Column(Float)

    # description of error in computing the quantity and/or rate formula.
    # either this or quantity and rate should be null at any given time,
    # never both or neither.
    error = Column(String(255))
    
    utilbill = relationship("UtilBill", backref=backref('charges', order_by=id,
                                                        cascade="all"))
    
    def __init__(self, utilbill, description, group, quantity, quantity_units,
                 rate, rsi_binding, total):
        """Construct a new :class:`.Charge`.
        
        :param utilbill: A :class:`.UtilBill` instance.
        :param description: A description of the charge.
        :param group: The charge group
        :param quantity: The quantity consumed
        :param quantity_units: The units of the quantity (i.e. Therms/kWh)
        :param rate: The charge per unit of quantity
        :param rsi_binding: The rate structure item corresponding to the charge
        :param total: The total charge (equal to rate * quantity) 
        """
        self.utilbill = utilbill
        self.description = description
        self.group = group
        self.quantity = quantity
        self.quantity_units = quantity_units
        self.rate = rate
        self.rsi_binding = rsi_binding
        self.total = total
        self.error = None

class Payment(Base):
    __tablename__ = 'payment'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    date_received = Column(DateTime, nullable=False)
    date_applied = Column(Date, nullable=False)
    description = Column(String)
    credit = Column(Float)

    customer = relationship("Customer", backref=backref('payments',
            order_by=id))

    '''date_received is the datetime when Skyline recorded the payment.
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
        self.date_received = date_received # datetime
        self.date_applied = date_applied   # date
        self.description = description
        self.credit = credit

    def to_dict(self):
        return {
            'id': self.id, 
            'date_received': self.date_received,
            'date_applied': self.date_applied,
            'description': self.description,
            'credit': self.credit,
            # the client uses this field to determine if users should be
            # allowed to edit this payment
            'editable': datetime.utcnow() - self.date_received \
                    < timedelta(hours=24)
        }

    def __repr__(self):
        return '<Payment(%s, received=%s, applied=%s, %s, %s)>' \
                % (self.customer.account, self.date_received, \
                        self.date_applied, self.description, self.credit)


# NOTE this is a view
class StatusDaysSince(Base):
    __tablename__ = 'status_days_since'

    # NOTE it seems that SQLAlchemy requires at least one column to be
    # identified as a "primary key" even though the table doesn't really have a
    # primary key in the db.
    account = Column(String, primary_key=True)
    dayssince = Column(Integer)

    def __init__(self, account, dayssince):
        self.account = account
        self.dayssince = dayssince

    def __repr__(self):
        return '<StatusDaysSince(%s, %s)>' \
                % (self.account, self.dayssince)


# TODO move the 2 functions below to Process? seems like state.py is only about
# the state database

def guess_utilbill_periods(start_date, end_date):
    '''Returns a list of (start, end) tuples representing a the number and
    periods of "hypothetical" utility bills covering the date range
    [start_date, end_date). "Hypothetical" utility bills are used for filling
    in a time gap between existing utility bills and a newly-uploaded one.'''
    if end_date <= start_date:
        raise ValueError('start date must precede end date.')

    # determine how many bills there are: divide total number of days by
    # hard-coded average period length of existing utilbills (computed using
    # utilbill_histogram.py), and round to nearest integer--but never go below
    # 1, since there must be at least 1 bill
    # TODO this hard-coded constant was the average period length of a sample
    # of many customers' utility bills; replace it with something smarter. we
    # should probably use a customer-specific average period length, since some
    # customers have 2-month utility bills.
    num_bills = max(1, int(round((end_date - start_date).days / 30.872)))

    # each bill's period will have the same length (except possibly the last
    # one)
    period_length = (end_date - start_date).days / num_bills

    # generate periods: all periods except the last have length
    # 'period_length'; last period may be slightly longer to fill up any
    # remaining space
    periods = []
    for i in range(num_bills-1):
        periods.append((start_date + timedelta(days= i * period_length),
                start_date + timedelta(days= (i + 1) * period_length)))
    periods.append((start_date + timedelta(days= (num_bills-1) * period_length),
        end_date))
    return periods


class StateDB(object):
    """A Data Access Class"""

    def __init__(self, logger=None):
        """Construct a new :class:`.StateDB`.

        :param session: a ``scoped_session`` instance
        :param logger: a logger object
        """
        self.logger = logger
        self.session = Session
        pass

    def get_customer(self, account):
        session = Session()
        return session.query(Customer).filter(Customer.account==account).one()

    def get_next_account_number(self):
        '''Returns what would become the next account number if a new account
        were created were created (highest existing account number + 1--we're
        assuming accounts will be integers, even though we always store them as
        strings).'''
        session = Session()
        last_account = max(map(int, self.listAccounts()))
        return last_account + 1

    def get_utilbill(self, account, service, start, end):
        session = Session()
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        return session.query(UtilBill)\
                .filter(UtilBill.customer_id==customer.id)\
                .filter(UtilBill.service==service)\
                .filter(UtilBill.period_start==start)\
                .filter(UtilBill.period_end==end).one()

    def get_utilbill_by_id(self, ubid):
        session = Session()
        return session.query(UtilBill).filter(UtilBill.id==ubid).one()

    def utilbills_for_reebill(self, account, sequence, version='max'):
        '''Returns all utility bills for the reebill given by account,
        sequence, version (highest version by default).'''
        session = Session()
        reebill = self.get_reebill(account, sequence, version=version)
        return session.query(UtilBill).filter(ReeBill.utilbills.any(),
                ReeBill.id == reebill.id).all()

    def max_version(self, account, sequence):
        # surprisingly, it is possible to filter a ReeBill query by a Customer
        # column even without actually joining with Customer. because of
        # func.max, the result is a tuple rather than a ReeBill object.
        session = Session()
        reebills_subquery = session.query(ReeBill).join(Customer)\
                .filter(ReeBill.customer_id==Customer.id)\
                .filter(Customer.account==account)\
                .filter(ReeBill.sequence==sequence)
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
        result = session.query(func.max(ReeBill.version))\
                .filter(ReeBill.customer == customer)\
                .filter(ReeBill.issued==1).one()[0]
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
        reebills = session.query(ReeBill).join(Customer)\
                .filter(Customer.account==account)\
                .filter(ReeBill.version > 0)\
                .filter(ReeBill.issued==0).all()
        return [(int(reebill.sequence), int(reebill.version)) for reebill
                in reebills]

    def discount_rate(self, account):
        '''Returns the discount rate for the customer given by account.'''
        session = Session()
        result = session.query(Customer).filter_by(account=account).one().\
                get_discount_rate()
        return result
        
    def late_charge_rate(self, account):
        '''Returns the late charge rate for the customer given by account.'''
        session = Session()
        result = session.query(Customer).filter_by(account=account).one()\
                .get_late_charge_rate()
        return result

    def last_sequence(self, account):
        '''Returns the sequence of the last reebill for 'account', or 0 if
        there are no reebills.'''
        session = Session()
        customer = self.get_customer(account)
        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id).one()[0]
        # TODO: because of the way 0.xml templates are made (they are not in
        # the database) reebill needs to be primed otherwise the last sequence
        # for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence =  0
        return max_sequence
        
    def last_issued_sequence(self, account,
            include_corrections=False):
        '''Returns the sequence of the last issued reebill for 'account', or 0
        if there are no issued reebills.'''
        session = Session()
        customer = self.get_customer(account)
        if include_corrections:
            filter_logic = sqlalchemy.or_(ReeBill.issued==1,
                    sqlalchemy.and_(ReeBill.issued==0, ReeBill.version>0))
        else:
            filter_logic = ReeBill.issued==1

        max_sequence = session.query(sqlalchemy.func.max(ReeBill.sequence)) \
                .filter(ReeBill.customer_id==customer.id) \
                .filter(filter_logic).one()[0]
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    def get_last_reebill(self, account, issued_only=False):
        '''Returns the highest-sequence, highest-version ReeBill object for the
        given account, or None if no reebills exist. if issued_only is True,
        returns the highest-sequence/version issued reebill.
        '''
        session = Session()
        customer = self.get_customer(account)
        cursor = session.query(ReeBill).filter_by(customer=customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version))
        if issued_only:
            cursor = cursor.filter_by(issued=True)
        if cursor.count() == 0:
            return None
        return cursor.first()

    def get_last_utilbill(self, account, service=None, utility=None,
            rate_class=None, end=None):
        '''Returns the latest (i.e. last-ending) utility bill for the given
        account matching the given criteria. If 'end' is given, the last
        utility bill ending before or on 'end' is returned.'''
        session = Session()
        cursor = session.query(UtilBill).join(Customer)\
                .filter(UtilBill.customer_id == Customer.id)\
                .filter(Customer.account == account)
        if service is not None:
            cursor = cursor.filter(UtilBill.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if end is not None:
            cursor = cursor.filter(UtilBill.period_end <= end)
        result = cursor.order_by(UtilBill.period_end).first()
        if result is None:
            raise NoSuchBillException("No utility bill found")
        return result

    def last_utilbill_end_date(self, account):
        '''Returns the end date of the latest utilbill for the customer given
        by 'account', or None if there are no utilbills.'''
        session = Session()
        customer = self.get_customer(account)
        query_results = session.query(sqlalchemy.func.max(UtilBill.period_end))\
                .filter(UtilBill.customer_id==customer.id).one()
        if len(query_results) > 0:
            return query_results[0]
        return None

    def new_reebill(self, account, sequence, version=0):
        '''Creates a new reebill row in the database and returns the new
        ReeBill object corresponding to it.'''
        session = Session()
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()
        new_reebill = ReeBill(customer, sequence, version)
        session.add(new_reebill)
        return new_reebill

    def issue(self, account, sequence, issue_date=datetime.utcnow()):
        '''Marks the highest version of the reebill given by account, sequence
        as issued.
        '''
        session = Session()
        reebill = self.get_reebill(account, sequence)
        if reebill.issued == 1:
            raise IssuedBillError(("Can't issue reebill %s-%s-%s because it's "
                    "already issued") % (account, sequence, reebill.version))
        reebill.issued = 1
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
        # test_state:StateTest.test_versions tested for it. 
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
                   .filter(Customer.account==account).one()
        except NoResultFound:
            return False
        return True

    def listAccounts(self):
        '''List of all customer accounts (ordered).'''    
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        session = Session()
        result = map((lambda x: x[0]),
                session.query(Customer.account)\
                .order_by(Customer.account).all())
        return result

    def list_accounts(self, start, limit):
        '''List of customer accounts with start and limit (for paging).'''
        # SQLAlchemy returns a list of tuples, so convert it into a plain list
        session = Session()
        query = session.query(Customer.account)
        slice = query[start:start + limit]
        count = query.count()
        result = map((lambda x: x[0]), slice)
        return result, count

    def listSequences(self, account):
        session = Session()

        # TODO: figure out how to do this all in one query. many SQLAlchemy
        # subquery examples use multiple queries but that shouldn't be
        # necessary
        customer = session.query(Customer).filter(Customer.account==account).one()
        sequences = session.query(ReeBill.sequence).with_lockmode("read") \
                .filter(ReeBill.customer_id==customer.id).all()

        # sequences is a list of tuples of numbers, so convert it into a plain list
        result = map((lambda x: x[0]), sequences)

        return result

    def listReebills(self, start, limit, account, sort, dir, **kwargs):
        session = Session()
        query = session.query(ReeBill).join(Customer)\
                .filter(Customer.account==account)
        
        if (dir == u'DESC'):
            order = desc
        elif (dir == u'ASC'):
            order = asc
        else:
            raise ValueError("Bad Parameter Value: 'dir' must be 'ASC' or 'DESC'")

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
        session = Session()
        for account in self.listAccounts():
            for sequence in self.listSequences(account):
                reebill = self.get_reebill(account, sequence)
                if include_unissued or reebill.issued:
                    yield account, int(sequence), int(reebill.max_version)

    def reebill_versions(self, include_unissued=True):
        '''Generates (account, sequence, version) tuples for all reebills in
        MySQL.'''
        session = Session()
        for account in self.listAccounts():
            for sequence in self.listSequences(account):
                reebill = self.get_reebill(account, sequence)
                if include_unissued or reebill.issued:
                    max_version = reebill.max_version
                else:
                    max_version = reebill.max_version - 1
                for version in range(max_version + 1):
                    yield account, sequence, version

    def get_reebill(self, account, sequence, version='max'):
        '''Returns the ReeBill object corresponding to the given account,
        sequence, and version (the highest version if no version number is
        given).'''
        session = Session()
        if version == 'max':
            version = session.query(func.max(ReeBill.version)).join(Customer) \
                .filter(Customer.account==account) \
                .filter(ReeBill.sequence==sequence).one()[0]
        result = session.query(ReeBill).join(Customer) \
            .filter(Customer.account==account) \
            .filter(ReeBill.sequence==sequence)\
            .filter(ReeBill.version==version).one()
        return result

    def get_reebill_by_id(self, rbid):
        session = Session()
        return session.query(ReeBill).filter(ReeBill.id==rbid).one()

    def get_descendent_reebills(self, account, sequence):
        session = Session()
        query = session.query(ReeBill).join(Customer) \
            .filter(Customer.account==account) \
            .order_by(ReeBill.sequence)

        slice = query[int(sequence):]

        return slice

    def list_utilbills(self, account, start=None, limit=None):
        '''Queries the database for account, start date, and end date of bills
        in a slice of the utilbills table; returns the slice and the total
        number of rows in the table (for paging). If 'start' is not given, all
        bills are returned. If 'start' is given but 'limit' is not, all bills
        starting with index 'start'. If both 'start' and 'limit' are given,
        returns bills with indices in [start, start + limit).'''
        session = Session()
        query = session.query(UtilBill).with_lockmode('read').join(Customer)\
                .filter(Customer.account==account)\
                .order_by(Customer.account, desc(UtilBill.period_start))

        if start is None:
            return query, query.count()
        if limit is None:
            return query[start:], query.count()
        return query[start:start + limit], query.count()

    def get_utilbills_on_date(self, account, the_date):
        '''Returns a list of UtilBill objects representing MySQL utility bills
        whose periods start before/on and end after/on 'the_date'.'''
        session = Session()
        return session.query(UtilBill).filter(
                UtilBill.customer==self.get_customer(account),
                UtilBill.period_start<=the_date,
                UtilBill.period_end>the_date).all()

    
    def fill_in_hypothetical_utilbills(self, account, service,
            utility, rate_class, begin_date, end_date):
        '''Creates hypothetical utility bills in MySQL covering the period
        [begin_date, end_date).'''
        # get customer id from account number
        session = Session()
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        for (start, end) in guess_utilbill_periods(begin_date, end_date):
            # make a UtilBill
            # note that all 3 Mongo documents are None
            utilbill = UtilBill(customer, UtilBill.Hypothetical, service,
                    utility, rate_class, period_start=start, period_end=end)
            # put it in the database
            session.add(utilbill)

    def trim_hypothetical_utilbills(self, account, service):
        '''Deletes hypothetical utility bills for the given account and service
        whose periods precede the start date of the earliest non-hypothetical
        utility bill or follow the end date of the last utility bill.'''
        session = Session()
        customer = self.get_customer(account)
        all_utilbills = session.query(UtilBill)\
                .filter(UtilBill.customer == customer)
        real_utilbills = all_utilbills\
                .filter(UtilBill.state != UtilBill.Hypothetical)
        hypothetical_utilbills = all_utilbills\
                .filter(UtilBill.state == UtilBill.Hypothetical)

        # if there are no real utility bills, delete all the hypothetical ones
        # (i.e. all of the utility bills for this customer)
        if real_utilbills.count() == 0:
            for hb in hypothetical_utilbills:
                session.delete(hb)
            return

        # if there are real utility bills, only delete the hypothetical ones
        # whose entire period comes before end of first real bill or after
        # start of last real bill
        first_real_utilbill = real_utilbills\
                .order_by(asc(UtilBill.period_start))[0]
        last_real_utilbill = session.query(UtilBill)\
                .order_by(desc(UtilBill.period_start))[0]
        for hb in hypothetical_utilbills:
            if (hb.period_start <= first_real_utilbill.period_end \
                    and hb.period_end <= first_real_utilbill.period_end)\
                    or (hb.period_end >= last_real_utilbill.period_start\
                    and hb.period_start >= last_real_utilbill.period_start):
                session.delete(hb)

    # NOTE deprectated in favor of UtilBillLoader.get_last_real_utilbill
    def get_last_real_utilbill(self, account, end, service=None,
            utility=None, rate_class=None, processed=None):
        '''Returns the latest-ending non-Hypothetical UtilBill whose
        end date is before/on 'end', optionally with the given service,
        utility, rate class, and 'processed' status.
        '''
        session = Session()
        session.query(UtilBill).all()
        return UtilBillLoader(session).get_last_real_utilbill(account, end,
                service=service, utility=utility, rate_class=rate_class,
                processed=processed)

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
        return new_payment

    def update_payment(self, oid, date_applied, description, credit):
        '''Sets the date_applied, description, and credit of the payment with
        id 'oid'.'''
        session = Session()
        payment = session.query(Payment).filter(Payment.id == oid).one()
        if isinstance(date_applied, basestring):
            payment.date_applied = datetime.strptime(date_applied,
                    "%Y-%m-%dT%H:%M:%S").date()
        else:
            payment.date_applied = date_applied
        payment.description = description
        payment.credit = credit

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
        payments = session.query(Payment)\
            .filter(Payment.customer_id == Customer.id) \
            .filter(Customer.account == account) \
            .filter(and_(Payment.date_applied >= periodbegin,
            Payment.date_applied < periodend)).all()
        return payments
        
    def get_total_payment_since(self, account, start, end=None):
        '''Returns sum of all account's payments applied on or after 'start'
        and before 'end' (today by default). If 'start' is None, the beginning
        of the interval extends to the beginning of time.
        '''
        assert isinstance(start, date)
        if end is None:
            end=datetime.utcnow().date()
        session = Session()
        payments = session.query(Payment)\
                .filter(Payment.customer==self.get_customer(account))\
                .filter(Payment.date_applied < end)
        if start is not None:
            payments = payments.filter(Payment.date_applied >= start)
        return float(sum(payment.credit for payment in payments.all()))

    def payments(self, account):
        '''Returns list of all payments for the given account ordered by
        date_received.'''
        session = Session()
        payments = session.query(Payment).join(Customer)\
            .filter(Customer.account==account).order_by(Payment.date_received).all()
        return payments

    def retrieve_status_days_since(self, sort_col, sort_order):
        # SQLAlchemy query to get account & dates for all utilbills
        session = Session()
        entityQuery = session.query(StatusDaysSince)

        # example of how db sorting would be done
        #if sort_col == 'dayssince' and sort_order == 'ASC':
        #    sortedQuery = entityQuery.order_by(asc(StatusDaysSince.dayssince))
        #elif sort_colr == 'dayssince' and sort_order == 'DESC':
        #    sortedQuery = entityQuery.order_by(desc(StatusDaysSince.dayssince))
        #lockmodeQuery = sortedQuery.with_lockmode("read")

        lockmodeQuery = entityQuery.with_lockmode("read")

        result = lockmodeQuery.all()

        return result

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
        state SkylineEstimated or lower) are included.
        '''
        cursor = self._session.query(UtilBill).filter(UtilBill.state <=
                UtilBill.SkylineEstimated)
        for key, value in kwargs.iteritems():
            cursor = cursor.filter(getattr(UtilBill, key) == value)
        return cursor

    def get_last_real_utilbill(self, account, end, service=None, utility=None,
                rate_class=None, processed=None):
        '''Returns the latest-ending non-Hypothetical UtilBill whose
        end date is before/on 'end', optionally with the given service,
        utility, rate class, and 'processed' status.
        '''
        customer = self._session.query(Customer).filter_by(account=account)\
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

