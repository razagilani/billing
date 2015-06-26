from datetime import datetime
from io import StringIO
import re

from dateutil import parser as dateutil_parser
from sqlalchemy import Column, Integer, Float, ForeignKey, String, Enum, \
    UniqueConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, RelationshipProperty, object_session, \
    MapperExtension
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound

from core import model
# from core.extraction import layout
# from core.extraction.layout import BoundingBox
from core.model import Charge, Session, Utility, Address, RateClass
from exc import MatchError, ConversionError, ExtractionError, ApplicationError


class Main(object):
    """Handles everything about the extraction process for a particular bill.
    Consumers only need to use this.
    """
    def __init__(self, bill_file_handler):
        self._bill_file_handler = bill_file_handler

    def extract(self, utilbill):
        """Update the given bill with data extracted from its file. An
        extractor is chosen automatically.
        :param utilbill: UtilBill
        """
        # try all extractors and use the one that works best, i.e. gets the
        # largest absolute number of fields.
        extractors = model.Session().query(Extractor).all()
        if len(extractors) == 0:
            return
        best_extractor = max(extractors, key=lambda e: e.get_success_count(
            utilbill, self._bill_file_handler))

        # values are cached so it's OK to call this repeatedly
        best_extractor.apply_values(utilbill, self._bill_file_handler,
                                    Applier.get_instance())

        utilbill.date_extracted = datetime.utcnow()

    def test_extractor(self, extractor, utilbills):
        """Check performance of the given Extractor on the given set of bills.
        :param extractor: Extractor to test
        :param utilbills: iterator of UtilBills.
        (too possibly avoid buffering the entire result set in memory, see
        https://stackoverflow.com/questions/7389759/memory-efficient-built-in
        -sqlalchemy-iterator-generator)
        :return: 3 ints: number of bills from which all fields could be
        extracted, number from which at least one field could be extracted,
        total number of bills
        """
        # TODO: a better way would be to test each extractor only on bills
        # that belong to its own layout, but there's no grouping by layouts yet.
        all_count, any_count, total_count = 0, 0, 0
        for utilbill in utilbills:
            c = extractor.get_success_count(utilbill, self._bill_file_handler)
            if c > 0:
                any_count += 1
            if c == len(extractor.fields):
                all_count += 1
            total_count += 1
        return all_count, any_count, total_count


class Applier(object):
    """Applies extracted values to attributes of UtilBill. There's no
    instance-specific state so only one instance is needed.

    To apply values to something other than a UtilBill, a superclass could be
    created that includes the non-UtilBill specific parts, and other subclasses
    of it would have different 'KEYS' and a different implementation of 'apply'.
    """
    @staticmethod
    def set_rate_class(bill, rate_class_name):
        """
        Given a bill and a rate class name, this function sets the rate class of the bill.
        If the name corresponds to an existing rate class in the database, then the existing rate class is used.
        Otherwise, a new rate class object is created.
        Note: This function uses the default service for all bills.
        :param bill: A UtilBill object
        :param rate_class_name:  A string, the name of the rate class
        """
        s = Session()
        bill_util = bill.get_utility()
        if bill_util is None:
            raise ApplicationError("Unable to set rate class for bill id %s: utility is unknown" % bill_util.id)
        q = s.query(RateClass).filter(RateClass.name == rate_class_name, RateClass.utility == bill_util)
        try:
            rate_class = q.one()
        except NoResultFound:
            rate_class = RateClass(utility=bill_util, name=rate_class_name)
        bill.rate_class = rate_class

    @staticmethod
    def set_charges(bill, charges):
        """Special function to apply a list of charges, because the a unit is
        required and may not be known. If possible, get rid of this function.
        """
        unit = bill.get_total_energy_unit()

        # unit will not be known if rate class is not set
        if unit is None:
            unit = 'kWh'

        for charge in charges:
            charge.unit = unit
        bill.charges = charges

    BILLING_ADDRESS = 'billing address'
    CHARGES = 'charges'
    END = 'end'
    ENERGY = 'energy'
    NEXT_READ = 'next read'
    RATE_CLASS = 'rate class'
    SERVICE_ADDRESS = 'service address'
    START = 'start'
    KEYS = {
        BILLING_ADDRESS: model.UtilBill.billing_address,
        CHARGES: set_charges.__func__,
        END: model.UtilBill.period_end,
        ENERGY: model.UtilBill.set_total_energy,
        NEXT_READ: model.UtilBill.set_next_meter_read_date,
        RATE_CLASS: set_rate_class.__func__,
        SERVICE_ADDRESS: model.UtilBill.service_address,
        START: model.UtilBill.period_start,
    }
    # TODO:
    # target_total (?)
    # supplier
    # utility (could be determined by layout itself)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls(cls.KEYS)
        return cls._instance

    def __init__(self, keys):
        self.keys = keys

    def apply(self, key, value, utilbill):
        """Set the value of a UtilBill attribute. Raise ApplicationError if
        anything goes wrong.
        :param key: one of KEYS (determines which UtilBill attribute gets
        the value)
        :param value: extracted value to be applied
        :param utilbill: UtilBill
        """
        attr = self.keys.get(key)
        if attr is None:
            raise ApplicationError('Unknown key "%s"' % key)

        # figure out how to apply the value based on the type of the attribute
        if callable(attr):
            if hasattr(utilbill, attr.__name__):
                method = getattr(utilbill, attr.__name__)
                # method of UtilBill
                apply = lambda: method(value)
            else:
                # other callable, such as method of this class.
                # it must take a UtilBill and the value to apply.
                apply = lambda: attr(utilbill, value)
        else:
            # non-method attribute
            if isinstance(attr.property, RelationshipProperty):
                # relationship attribute
                attr_name = attr.property.key
            elif isinstance(attr, InstrumentedAttribute):
                # regular column atttribute
                attr_name = attr.property.columns[0].name
                # catch type error before the value gets saved in db
                the_type = attr.property.columns[0].type.python_type
                if not isinstance(value, the_type):
                    raise ApplicationError('Expected type %s, got %s %s' % (
                        the_type, type(value), value))
            else:
                raise ApplicationError(
                    "Can't apply %s to %s: unknown attribute type %s" % (
                        value, attr, type(attr)))
            apply = lambda: setattr(utilbill, attr_name, value)

        # do it
        try:
            apply()
        except Exception as e:
            raise ApplicationError('%s: %s' % (e.__class__, e.message))


def convert_wg_charges_std(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_name_map = Session().query(Utility).filter_by(name='washington gas').one().charge_name_map
    regexflags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    groups = r'DISTRIBUTION SERVICE(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*?)TAXES(.*?' \
             r'Total Current Washington Gas Charges)(.*?)' \
             r'Total Washington Gas Charges This Period'
    charge_name_exp = r"([a-z]['a-z \-]+?[a-z])\s*(?:[\d@\n]|$)"
    dist_charge_block, supply_charge_block, taxes_charge_block, charge_values_block = re.search(groups, text, regexflags).groups()
    dist_charge_names = re.findall(charge_name_exp, dist_charge_block, regexflags)
    supply_charge_names = re.findall(charge_name_exp, supply_charge_block, regexflags)
    taxes_charge_names = re.findall(charge_name_exp, taxes_charge_block, regexflags)
    charge_values_lines = filter(None, re.split("\n+", charge_values_block,
        regexflags))

    #read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_lines = charge_values_lines[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)
    charges = []
    for names, type in charge_data:
        for charge_name in names:
            if not charge_values_lines:
                break
            charge_value_text = charge_values_lines[0]
            del charge_values_lines[0]
            match = re.search(r"\$\s+(-?\d+(?:\.\d+)?)", charge_value_text)
            if not match:
                continue
            charge_value = float(match.group(1))
            charges.append(process_charge(charge_name, charge_value, type))
    #reverse list, remove last item ('Total Current Washington Gas Charges')
    return charges[:0:-1]

def convert_wg_charges_wgl(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_name_map = Session().query(Utility).filter_by(
        name='washington gas').one().charge_name_map
    groups = 'DISTRIBUTION SERVICE(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*)TAXES(.*?)' \
             'Total Current Washington Gas Charges(.*?)' \
             'Total Washington Gas Charges This Period'
    regexflags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    dist_charge_block, supply_charge_block, taxes_charge_block, charge_values_block = re.search(groups, text, regexflags)
    dist_charge_names = re.split("\n+", dist_charge_block, regexflags)
    supply_charge_names = re.split("\n+", supply_charge_block, regexflags)
    taxes_charge_names = re.split("\n+", taxes_charge_block, regexflags)
    charge_values_names = re.split("\n+", charge_values_block, regexflags)

    charge_name_exp = r"([a-z]['a-z ]+?[a-z])\s*[\d@\n]"
    #read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_names = charge_values_names[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    for names, type in charge_data:
        for n in names:
            if not charge_values_names:
                break
            charge_value_text = charge_values_names[0]
            del charge_values_names[0]
            match = re.search(r"\$\s+(-?\d+(?:\.\d+)?)", charge_value_text)
            if not match:
                continue
            charge_value = float(match.group(1))

            match = re.search(charge_name_exp, n, regexflags)
            if not match:
                continue
            charge_name = match.group(1)

            charges.append(process_charge(charge_name, charge_value, type))

    return charges

def pep_old_convert_charges(text):
    """
    Given text output from a pepco utility bill PDF that contains supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """
    #TODO deal with external suppliers
    #TODO find a better method for categorizing charge names
    charge_name_map = Session().query(Utility).filter_by(
        name='pepco').one().charge_name_map


    distribution_charges_exp = r'Distribution Services:(.*?)Generation Services:'
    supply_charges_exp = r'Generation Services:(.*?)Transmission Services:'
    transmission_charges_exp = r'Transmission Servces:(.*?Total Charges - Transmission)'
    charge_values_exp = r'Total Charges - Transmission(.*?)CURRENT CHARGES THIS PERIOD'

    regex_flags =  re.DOTALL | re.IGNORECASE | re.MULTILINE
    dist_charges_block = re.search(distribution_charges_exp, text, regex_flags).group(1)
    supply_charges_block = re.search(supply_charges_exp, text, regex_flags).group(1)
    trans_charges_block = re.search(transmission_charges_exp, text, regex_flags).group(1)
    charge_values_block = re.search(charge_values_exp, text, regex_flags).group(1)

    dist_charges_names = re.split(r"\n+", dist_charges_block, regex_flags)
    supply_charges_names = re.split(r"\n+", supply_charges_block, regex_flags)
    trans_charges_names = re.split(r"\n+", trans_charges_block, regex_flags)
    charge_values = re.split(r"\n+", charge_values_block, regex_flags)
    trans_charges_names_clean = []
    # clean rate strings (eg 'at 0.0000607 per KWH') from transmission charges.
    for name in trans_charges_names:
        if not name or re.match(r'\d|at|Includ|Next', name):
            continue
        trans_charges_names_clean.append(name)

    def process_charge(name, value, ct):
        rsi_binding = charge_name_map.get(name, name.upper().replautce(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    charge_data = [(dist_charges_names, Charge.DISTRIBUTION), (supply_charges_names, Charge.SUPPLY), (trans_charges_names_clean, Charge.DISTRIBUTION)]
    for names, type in charge_data:
        for charge_name in names:
            if not charge_name:
                continue
            # in case some charges failed to be read
            if not charge_values:
                break
            charge_num_text = charge_values[0]
            del charge_values[0]
            charge_num = float(re.search(r'\d+(?:\.\d+)?', charge_num_text))
            charges.append(process_charge(charge_name, charge_num, type))

    return charges


def pep_new_convert_charges(text):
    """
    Given text output from a pepco utility bill PDF that contains supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """

    charge_name_map = Session().query(Utility).filter_by(name='pepco').one().charge_name_map

    #in pepco bills, supply and distribution charges are separate
    distribution_charges_exp = r'Distribution Services:(.*?)(Status of your Deferred|Page)'
    supply_charges_exp = r'Transmission Services\:(.*?)Energy Usage History'
    dist_text = re.search(distribution_charges_exp, text).group(1)
    supply_text = re.search(supply_charges_exp, text).group(1)

    #regexes for individual charges
    exp_name = r'([A-Z][A-Za-z \(\)]+?)' #Letters, spaces, and parens (but starts with capital letter)
    exp_stuff = r'(?:(?:Includes|at\b|\d).*?)?' #stuff in between the name and value, like the per-unit rate
    exp_value = r'(\d[\d\.]*)' # The actual number we want
    exp_lookahead = r'(?=[A-Z]|$)' # The next charge name will begin with a capital letter.
    charge_exp = re.compile(exp_name + exp_stuff + exp_value + exp_lookahead)

    def process_charge(p, ct):
        name = p[0]
        value = float(p[1])
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    for charge_text, charge_type in [(dist_text, Charge.DISTRIBUTION), (supply_text, Charge.SUPPLY)]:
        charges.extend([process_charge(c, charge_type) for c in charge_exp.findall(charge_text)])

    return charges

def convert_address(text):
    '''
    Given a string containing an address, parses the address into an Address object in the database.
    '''
    #matches city, state, and zip code
    regional_exp = r'(\w+)\s+([a-z]{2})\s+(\d{5}(?:-\d{4})?)'
    #for attn: line in billing addresses
    attn_co_exp = r"(?:(?:attn:?|C/?O) )+(.*)$$"
    #A PO box, or a line that starts with a number
    street_exp = r"(\d+.*$|PO BOX \d+)"

    addressee = city = state = postal_code = None
    lines = re.split("\n+", text, re.MULTILINE)

    for line in lines:
        #if line has "attn:" in it, this is the addresse
        match = re.search(attn_co_exp, line, re.IGNORECASE)
        if match:
            addressee = match.group(1)
            continue
        #if it a po box or starts with a number, this line is a street address
        match = re.search(street_exp, line, re.IGNORECASE)
        if match:
            street = match.group(1)
            continue
        # check if this line contains city/state/zipcode
        match = re.search(regional_exp, line, re.IGNORECASE)
        if match:
            city, state, postal_code = match.groups
            continue
        #if none of the above patterns match, assume that this line is the addresse
        addressee = line
    return Address(addressee=addressee, street=street, city=city, state=state, postal_code=postal_code)

def convert_rate_class(text):
    s = Session()
    q = s.query(RateClass).filter(RateClass.name == text)
    try:
        return q.one()
    except NoResultFound:
        #TODO fill in fields correctly
        return RateClass(name=text)

class Field(model.Base):
    """Recipe for extracting one piece of data from a larger amount of input
    data. All values are initially strings, and a separate function is used
    to convert the string into its destination type (which could be another
    string, a number, or something complicated like a list of Charge objects).

    This is an abstract class.
    """
    class FieldExtension(MapperExtension):
        """Handles automatically updating Extractor.modified when a Field
        belonging to the extractor has been added, changed, or removed.
        """
        def before_insert(self, mapper, connection, instance):
            # TODO: better to use SQL function (func.now()), if it worked
            instance.extractor.modified = datetime.utcnow()

        def before_update(self, mapper, connection, instance):
            if object_session(instance).is_modified(instance,
                    include_collections=False):
                instance.extractor.modified = datetime.utcnow()

        def before_delete(self, mapper, connection, instance):
            instance.extractor.modified = datetime.utcnow()

    # various functions can be used to convert strings into other types. each
    #  one has a name so it can be stored in the database.
    ADDRESS = 'address'
    DATE = 'date'
    FLOAT = 'float'
    STRING = 'string'
    WG_CHARGES = 'wg charges'
    WG_CHARGES_WGL = 'wg charges wgl'
    PEPCO_OLD_CHARGES = 'pepco old charges'
    PEPCO_NEW_CHARGES = 'pepco new charges'
    TYPES = {
        ADDRESS: convert_address,
        DATE: lambda x: dateutil_parser.parse(x).date(),
        FLOAT: lambda x: float(x.replace(',','')),
        STRING: unicode,
        WG_CHARGES: convert_wg_charges_std,
        WG_CHARGES_WGL: convert_wg_charges_wgl,
        PEPCO_OLD_CHARGES: pep_old_convert_charges,
        PEPCO_NEW_CHARGES: pep_new_convert_charges,
    }

    __tablename__ = 'field'
    field_id = Column(Integer, primary_key=True)
    discriminator = Column(String, nullable=False)

    # each Extractor subclass is associated with a Field subclass; in order
    # to get Flask-Admin to work with these classes, the relationships must
    # be defined in the subclasses (e.g. TextExtractor to TextField).
    extractor_id = Column(Integer, ForeignKey('extractor.extractor_id'))

    type = Column(Enum(*TYPES.keys(), name='field_type'))

    # string determining how the extracted value gets applied to a UtilBill
    applier_key = Column(Enum(*Applier.KEYS.keys(), name='applier_key'))

    __table_args__ = (UniqueConstraint('extractor_id', 'applier_key'),)
    __mapper_args__ = {
        'extension': FieldExtension(),
        'polymorphic_on': discriminator,
        'polymorphic_identity': 'field',
    }

    # cached input data and extracted value (only meant to be used as
    # instance variables)
    _input = None
    _value = None

    def __init__(self, type=STRING, *args, **kwargs):
        """
        :param type: one of the named type constants, determines how to
        convert the extracted string value to the appropriate type.
        """
        super(Field, self).__init__(type=type, *args, **kwargs)

    def _extract(self, input):
        """Extract a string from "input".
        :param input: input data (e.g. text, image)
        :return: extracted value (string)
        """
        # subclasses need to override this
        raise NotImplementedError

    def get_value(self, input):
        """Extract a value from "input" and convert it to an appropriate type.
        Values are cached if the same input is repeated.
        :param input: input data (e.g. text, image)
        :return: final value ready to be applied to a UtilBill.
        """
        assert input is not None
        type_convert_func = self.TYPES[self.type]
        if self._value is None or input != self._input:
            self._input = input
            value_str = self._extract(input)
            try:
                value = type_convert_func(value_str)
            except Exception as e:
                raise ConversionError(
                    "Couldn't convert \"%s\" using function %s for type "
                    "\"%s\": %s" % (
                        value_str, type_convert_func, self.type, e))
            self._value = value
        return self._value



class Extractor(model.Base):
    """Updates a UtilBill with data taken from its file. Has a list of Fields,
    each of which extracts a particular value.

    Each Extractor belongs to a particular bill layout, but a layout could
    have more than one Extractor (for different input types like text/PDF/image,
    or different ways methods of processing the same kind of input).
    """
    __tablename__ = 'extractor'
    extractor_id = Column(Integer, primary_key=True)
    discriminator = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created = Column(DateTime, nullable=False, server_default=func.now())
    modified = Column(DateTime, nullable=False, server_default=func.now(),
                      onupdate=func.now())
    fields = relationship(Field, backref='extractor')

    __mapper_args__ = {
        'polymorphic_on': discriminator,
        'polymorphic_identity': 'extractor',
    }

    # instance variable to hold cached input data
    _input = None

    def _prepare_input(self, utilbill, bill_file_handler):
        """Subclasses should override to prepare input data to be used by Fields
        (eg text or image).
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler used to get the PDF file.
        :return: input data in whatever form is expected by Fields.
        """
        raise NotImplementedError

    #TODO right now this is a private method, we should make it public
    def _get_values(self, utilbill, bill_file_handler):
        """
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler
        :return: list of (field, extracted value) pairs for fields that
        succeeded in extracted values, and list of ExtractionErrors for fields
        that failed.
        """
        self._input = self._prepare_input(utilbill, bill_file_handler)
        good, errors = [], []
        for field in self.fields:
            try:
                value = field.get_value(self._input)
            except ExtractionError as error:
                errors.append(error)
            else:
                good.append((field, value))
        return good, errors

    def get_success_count(self, utilbill, bill_file_handler):
        """
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler
        :return: number of fields that could be extracted (int)
        """
        good, _ = self._get_values(utilbill, bill_file_handler)
        return len(good)

    def apply_values(self, utilbill, bill_file_handler, applier):
        """Update attributes of the given bill with data extracted from its
        file. Return value can be used to compare success rates of different
        Extractors.
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler to get files for UtilBills.
        :param applier: Applier that determines how values are applied
        :return number of fields successfully extracted (integer), list of
        ExtractionErrors
        """
        good, errors = self._get_values(utilbill, bill_file_handler)
        success_count = 0
        for field, value in good:
            try:
                applier.apply(field.applier_key, value, utilbill)
            except ApplicationError as error:
                errors.append(error)
            else:
                success_count += 1
        return success_count, errors


class TextExtractor(Extractor):
    """Extracts data about a bill from plain text dump of a PDF file.
    """
    __mapper_args__ = {'polymorphic_identity': 'textextractor'}

    class TextField(Field):
        """Field that extracts data from text input using a regular expression.
        """
        __mapper_args__ = {'polymorphic_identity': 'textfield'}

        @declared_attr
        def regex(cls):
            "regex column, if not present already."
            return Field.__table__.c.get('regex', Column(String,
                nullable=False))

        def __init__(self, *args, **kwargs):
            super(TextExtractor.TextField, self).__init__(*args, **kwargs)

        def _extract(self, text):
            m = re.search(self.regex, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)

            if m is None or len(m.groups()) != 1:
                raise MatchError(
                    'No match for pattern "%s" in text starting with "%s"' % (
                        self.regex, text[:20]))
            return m.groups()[0]

    #fields = relationship(TextField, backref='extractor')

    def _prepare_input(self, utilbill, bill_file_handler):
        """Return text dumped from the given bill's PDF file.
        """
        return utilbill.get_text(bill_file_handler)

class LayoutExtractor(Extractor):
    """
    Extracts data about a bill based on the layout of text in the PDF
    """
    __mapper_args__ = {'polymorphic_identity': 'layoutextractor'}

    class BoundingBoxField(Field):
        """
        A field that extracts text that is within a given bounding box on the PDF
        """
        __mapper_args__ = {'polymorphic_identity': 'boundingboxfield'}

        # First page is numbered 1, not 0
        page_num = Column(Integer)
        @declared_attr
        def regex(cls):
            "regex column, if not present already."
            return Field.__table__.c.get('regex', Column(String,
                nullable=False))

        #bounding box coordinates
        bbminx = Column(Float, nullable=True)
        bbminy = Column(Float, nullable=True)
        bbmaxx = Column(Float, nullable=True)
        bbmaxy = Column(Float, nullable=True)

        def __init__(self, *args, **kwargs):
            super(LayoutExtractor.BoundingBoxField, self).__init__(*args, **kwargs)

        def _extract(self, pages):
            if self.page_num > len(pages):
                raise ExtractionError('Not enough pages. Could not get page '
                                      '%d out of %d.' % (self.page_num,
                len(pages)))

            text = layout.get_text_from_boundingbox(pages[self.page_num - 1],
                BoundingBox(minx=self.bbminx, miny=self.bbminy,
                    maxx=self.bbmaxx, maxy=self.bbmaxy))

            if not self.regex:
                return text

            m = re.search(self.regex, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if m is None or len(m.groups()) != 1:
                raise MatchError(
                    'No match for pattern "%s" in text starting with "%s"' % (
                        self.regex, text[:20]))
            return m.groups()[0].strip()

    #TODO
    class TableField(Field):
        """
        A field that represents tabular data, within a given bounding box
        Each row is extracted as a tuple of data
        """

    def _prepare_input(self, utilbill, bill_file_handler):
        #TODO set up kdtree for faster object lookup
        return utilbill.get_layout(bill_file_handler)

class ExtractorResult(model.Base):
    __tablename__ = 'extractor_result'

    extractor_result_id = Column(Integer, primary_key=True)
    extractor_id = Column(Integer, ForeignKey('extractor.extractor_id'))
    task_id = Column(String, nullable=False)
    # date when the test was started, and finished (if it has finished)
    started = Column(DateTime, nullable=False)
    finished = Column(DateTime)

    # used when filtering bills by utility
    utility_id = Column(Integer, ForeignKey('utility.id'))

    # results to be filled in after the test has finished
    all_count = Column(Integer)
    any_count = Column(Integer)
    total_count = Column(Integer)
    #TODO should find a way to sync these with UtilBill's list of fields
    # field counts
    field_billing_address = Column(Integer)
    field_charges = Column(Integer)
    field_end = Column(Integer)
    field_energy = Column(Integer)
    field_next_read = Column(Integer)
    field_rate_class = Column(Integer)
    field_start = Column(Integer)
    field_service_address = Column(Integer)
    # field counts by month
    billing_address_by_month = Column(HSTORE)
    charges_by_month = Column(HSTORE)
    end_by_month = Column(HSTORE)
    energy_by_month = Column(HSTORE)
    next_read_by_month = Column(HSTORE)
    rate_class_by_month = Column(HSTORE)
    service_address_by_month = Column(HSTORE)
    start_by_month = Column(HSTORE)

    def set_results(self, metadata):
        """Fill in count fields after the test has finished.
        :param metadata: Celery task metadata/info dictionary.
        """
        self.finished = datetime.utcnow()
        self.all_count = metadata['all_count']
        self.any_count = metadata['any_count']
        self.total_count = metadata['total_count']

        # update overall count and count by month for each field
        for field_name in Applier.KEYS.iterkeys():
            attr_name = field_name.replace(" ", "_")
            count_for_field = metadata['fields'][field_name]
            setattr(self, "field_" + attr_name, count_for_field)
            date_count_dict = {str(date): str(counts.get(field_name, 0)) for
                               date, counts in metadata['dates'].iteritems()}
            setattr(self, attr_name + "_by_month", date_count_dict)
