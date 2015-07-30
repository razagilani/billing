from StringIO import StringIO
import ast
from datetime import datetime, date
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
from sqlalchemy import CheckConstraint, Column, String, Integer, ForeignKey, \
    Date, Boolean, Float, DateTime, Enum, inspect
from sqlalchemy.orm import relationship, backref, object_session
import tsort
from core.model import Base, Address, Session, Register
from core.model.model import UtilbillCallback, PHYSICAL_UNITS
from exc import NotProcessable, UnEditableBillError, BillingError, \
    BillStateError, MissingFileError, FormulaSyntaxError, FormulaError


class UtilBill(Base):
    POLYMORPHIC_IDENTITY = 'utilbill'

    __tablename__ = 'utilbill'

    __table_args__ = (CheckConstraint('period_start > \'1900-01-01\''),
                    CheckConstraint('period_end > \'1900-01-01\''),
                    CheckConstraint('next_meter_read_date > \'1900-01-01\''),
                    CheckConstraint('due_date > \'1900-01-01\''),
                    CheckConstraint('date_received > \'1900-01-01\''),
                    CheckConstraint('date_modified > \'1900-01-01\''),
                    CheckConstraint('date_scraped > \'1900-01-01\''))
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

    # which Extractor was used to get data out of the bill file, and when
    date_extracted = Column('date_scraped', DateTime, )

    # cached text taken from a PDF for use with TextExtractor
    _text = Column('text', String)

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

    def set_supplier(self, supplier):
        """Set the supplier, and set the supply group to None if the supplier is
        different from the current one.
        :param Supplier: Utility or None
        """
        if supplier != self.supplier:
            self.set_supply_group(None)
        self.supplier = supplier

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

    def __repr__(self):
        return ('<UtilBill(utility_account=<%s>, service=%s, period_start=%s, '
                'period_end=%s, state=%s)>') % (
                   self.utility_account.account, self.get_service(),
                   self.period_start, self.period_end, self.state)

    def add_charge(self, charge_kwargs):
        """
        :param charge_kwargs: arguments to create a Charge object (this is
        bad: pass a Charge object itself)
        :param fuzzy_pricing_model: FuzzyPricingModel, needed to guess the
        values of certain Charge attributes
        :return: new Charge object
        """
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

        # pre-fill a likely formula (Register.TOTAL now exists in every bill)
        if 'formula' not in charge_kwargs:
            charge.quantity_formula = Charge.get_simple_formula(Register.TOTAL)
            # since 'rsi_binding' is not a real value yet, it doesn't make
            # sense to try to pre-fill quantity and rate based on it

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
        errors and charges that have has_charge=False.
        """
        return sum(
            charge.total for charge in self.charges if charge.total is not
            None and charge.has_charge
        )

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

    def get_total_energy_unit(self):
        """:return: name of unit for measuring total energy (string), or None
        if this is unknown, which will happen if the rate class is not known.
        """
        if self.rate_class is None:
            assert self._registers == []
            return None
        total_register = self.get_register_by_binding(Register.TOTAL)
        return total_register.unit

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

    def replace_estimated_with_complete(self, other, bill_file_handler):
        """Convert an estimated bill, which has no file, into a real bill by
        copying all data from another non-estimated bill to this one, and
        deleting the other bill.
        :param other: UtilBill
        :param bill_file_handler: BillFileHandler
        """
        # validation
        self.check_editable()
        if self.state != self.Estimated:
            raise BillStateError("Bill to replace must be estimated")
        if other.state == self.Estimated:
            raise BillStateError("Replacement bill must not be estimated")
        assert self.sha256_hexdigest in ('', None)
        bill_file_handler.check_file_exists(other)

        # copy the data and update 'state'
        self._copy_data_from(other)

        # special case for the two Address objects which are technically
        # parents but should be copied like children
        # TODO: figure out how to handle this case correctly in
        # Base._copy_data_from
        self.billing_address = other.billing_address.clone()
        self.service_address = other.service_address.clone()

        assert self.sha256_hexdigest is not None
        bill_file_handler.check_file_exists(self)
        self.state = self.Complete

        # delete the other bill
        s = object_session(other)
        if s is not None:
            if inspect(other).pending:
                s.expunge(other)
            else:
                s.delete(other)

    def get_text(self, bill_file_handler, pdf_util):
        """Return text dump of the bill's PDF.
        :param bill_file_handler: used to get the PDF file (only if the text for
        this bill is not already cached).
        :param pdf_util: PDFUtil object used to parse the PDF file
        """
        if self._text in (None, ''):
            infile = StringIO()
            try:
                bill_file_handler.write_copy_to_file(self, infile)
            except MissingFileError as e:
                text = ''
            else:
                text = pdf_util.get_pdf_text(infile)
            self._text = text
        return self._text

    def get_layout(self, bill_file_handler):
        """
        Returns a list of LTPage objects, containing PDFMiner's layout
        information for the PDF
        :param bill_file_handler: used to get the PDF file
        """
        #TODO cache layout info after retrieval
        # maybe use 'PickleType' sqlalchemy column?
        pages = []
        infile = StringIO()
        try:
            bill_file_handler.write_copy_to_file(self, infile)
        except MissingFileError as e:
            print e
        else:
            # TODO: code for parsing PDF files probably doesn't belong in
            # UtilBill; maybe in BillFileHandler or extraction
            infile.seek(0)
            parser = PDFParser(infile)
            document = PDFDocument(parser)
            rsrcmgr = PDFResourceManager()
            laparams = LAParams()
            device = PDFPageAggregator(rsrcmgr, laparams=laparams)
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            try:
                for page in PDFPage.create_pages(document):
                    interpreter.process_page(page)
                    pages.append(device.get_result())
            except PDFSyntaxError as e:
                pages = []
                print e
            device.close()

        return pages


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


class Charge(Base):
    """Represents a specific charge item on a utility bill.
    """
    __tablename__ = 'charge'

    # allowed units for "quantity" field of charges
    CHARGE_UNITS = PHYSICAL_UNITS.keys() + ['dollars']
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

    # optional human-readable name of the charge as displayed on the bill
    name = Column(String(1000))

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

    def __init__(self, rsi_binding, name=None, formula='', rate=0,
                 target_total=None, description='', unit='', has_charge=True,
                 shared=False, roundrule="", type=DISTRIBUTION):
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
        self.name = name
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