from datetime import datetime
import re

from dateutil import parser as dateutil_parser
from sqlalchemy import Column, Integer, ForeignKey, String, Enum, \
    UniqueConstraint
from sqlalchemy.orm import relationship, RelationshipProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute

from core import model
from core.model import Charge, Session, Utility
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
        :param utilbills: list of UtilBills. inefficient but apparently there
        is no easy to way to avoid buffering the entire result set in memory?
        https://stackoverflow.com/questions/7389759/memory-efficient-built-in
        -sqlalchemy-iterator-generator
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
    """Applies extracted values to attributes of UtilBill.
    """
    CHARGES = 'charges'
    END = 'end'
    ENERGY = 'energy'
    NEXT_READ = 'next read'
    START = 'start'
    KEYS = {
        CHARGES: model.UtilBill.charges,
        END: model.UtilBill.period_end,
        ENERGY: model.UtilBill.set_total_energy,
        NEXT_READ: model.UtilBill.set_next_meter_read_date,
        START: model.UtilBill.period_start,
    }
    # TODO:
    # addresses
    # target_total (?)
    # supplier, rate class
    # utility (could be determined by layout itself)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls(cls.KEYS)
        return cls._instance

    # TODO: maybe there is no need for any Applier instances other than the
    # "normal" one returned by get_instance.
    def __init__(self, keys):
        self.keys = keys

    def apply(self, key, value, utilbill):
        """Set the value of a UtilBill attribute.
        :param key: one of KEYS (determines which UtilBill attribute gets
        the value)
        :param value: extracted value to be applied
        :param utilbill: UtilBill
        """
        attr = self.keys.get(key)
        if attr is None:
            raise ApplicationError('Unknown key "%s"' % key)
        if callable(attr):
            # method
            method_name = attr.__name__
            method = getattr(utilbill, method_name)
            apply = lambda: method(value)
        else:
            # column
            if isinstance(attr.property, RelationshipProperty):
                attr_name = attr.property.key
            elif isinstance(attr, InstrumentedAttribute):
                attr_name = attr.property.columns[0].name
                # catch type error before the value gets saved in db
                the_type = attr.property.columns[0].type.python_type
                if not isinstance(value, the_type):
                    raise ApplicationError('Expected type %s, got %s %s' % (
                        the_type, type(value), value))
            else:
                raise ValueError
            apply = lambda: setattr(utilbill, attr_name, value)
        # TODO: values could get applied in ways other than these, especially
        # in the case of non-scalar attributes like a group of charges

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
    charge_name_map = Session().query(Utility).filter_by(
    name='washington gas').one().charge_name_map

    groups = '.*DISTRIBUTION SERVICE(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*?)TAXES(.*)'
    num = r'[\d.]*'
    charge_total = r'\$\s*' + num
    charge_stuff = (r'\s*' + num + r'\s*(?:TH\s*)?(?:@\s*' + num
                    + ')?(?:x\s*)?' + num + r'\s*' + charge_total + r'\s*')
    charge_name = r'[A-Za-z- -]+'
    charge = r'\s*(' + charge_name + charge_stuff + r')\s*'
    d_charges, s_charges, tax_charges = re.match(groups, text, re.IGNORECASE).groups()
    d_charge_strs = re.findall(charge, d_charges)
    s_charge_strs = re.findall(charge, s_charges)
    tax_charge_strs = re.findall(charge, tax_charges)

    def extract_charge(charge_str, charge_type):
        name = re.match(charge_name, charge_str).group(0).strip()
        # "*?" means non-greedy *
        total_str = re.match(r'.*?(' + num + r')\s*$', charge_str).group(1)

        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(total_str),
                      type=charge_type)

    charges = []
    for charge_type, charge_texts in [(Charge.DISTRIBUTION, d_charge_strs),
                                      (Charge.SUPPLY, s_charge_strs),
                                      (Charge.DISTRIBUTION, tax_charge_strs)]:
        charges.extend([extract_charge(t, charge_type) for t in charge_texts])
    return charges

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
    groups = '.*DISTRIBUTION SERVICE(.*?)TAXES(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*)'
    num = r'[\d.]*'
    charge_total = r'\$\s*' + num
    charge_stuff = (r'\s*' + num + r'\s*(?:TH\s*)?(?:@\s*' + num
                    + ')?(?:x\s*)?' + num + r'\s*' + charge_total + r'\s*')
    charge_name = r'[A-Za-z- -]+'
    charge = r'\s*(' + charge_name + charge_stuff + r')\s*'
    d_charges, s_charges, tax_charges = re.match(groups, text, re.IGNORECASE).groups()
    d_charge_strs = re.findall(charge, d_charges)
    s_charge_strs = re.findall(charge, s_charges)
    tax_charge_strs = re.findall(charge, tax_charges)

    def extract_charge(charge_str, charge_type):
        name = re.match(charge_name, charge_str).group(0).strip()
        # "*?" means non-greedy *
        total_str = re.match(r'.*?(' + num + r')\s*$', charge_str).group(1)

        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(total_str),
                      type=charge_type)

    charges = []
    for charge_type, charge_texts in [(Charge.DISTRIBUTION, d_charge_strs),
                                      (Charge.SUPPLY, s_charge_strs),
                                      (Charge.DISTRIBUTION, tax_charge_strs)]:
        charges.extend([extract_charge(t, charge_type) for t in charge_texts])
    return charges

def pep_old_convert_charges(text):
    """
    Given text output from a pepco utility bill PDF that contains supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """
    #TODO find a better method for categorizing charge names
    charge_name_map = Session().query(Utility).filter_by(
        name='pepco').one().charge_name_map

    #in pepco bills, supply and distribution charges are separate
    distribution_charges_exp = r'Distribution Services\:(.*?)CURRENT CHARGES'
    supply_charges_exp = r'Generation and Transmission.*?\d{4}\:(.*?)Charges This Period'
    text = re.sub(r'at (\d)', r' \1', text) #remove the "at"s at the end of charge name, ie "Trust Fundat 0.0020500 per..."
    dist_text = re.search(distribution_charges_exp, text).group(1)
    supply_text = re.search(supply_charges_exp, text).group(1)

    def process_charge(p, ct):
        name = p[0]
        value = float(p[1])
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    #matches a price (ie a number that end in ".##"), or a capitalized word that is not 'KWH'
    price_exp = r'\d+\.\d{2}'
    name_exp = r'[A-Z][A-Za-z ]+'
    tokenizer_exp = r'(' + price_exp + '(?=[^\d]|' + price_exp + '))|(?:KWH(?: x )?)|(' + name_exp + ')'
    charges = []
    #looks at tokens one by one, and matches up names and numbers.
    #Reasoning is that a pair of corresponding name and number can be in reversed order, but still adjacent to each other.
    for section, type in [(dist_text, Charge.DISTRIBUTION), (supply_text, Charge.SUPPLY)]:
        charge_data_pairs = []
        tokens = re.findall(tokenizer_exp, section)
        name_tmp=''
        value_tmp=''
        for t in tokens:
            #if token is a number:
            if t[0]:
                if name_tmp:
                    charge_data_pairs.append((name_tmp, t[0]))
                    name_tmp = ''
                else:
                    value_tmp = t[0]
            #if token is a name:
            elif t[1]:
                if value_tmp:
                    charge_data_pairs.append((t[1], value_tmp))
                    value_tmp = ''
                else:
                    name_tmp = t[1]
        for cdp in charge_data_pairs:
            charges.append(process_charge(cdp, type))

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

class Field(model.Base):
    """Recipe for extracting one piece of data from a larger amount of input
    data. All values are initially strings, and a separate function is used
    to convert the string into its destination type (which could be another
    string, a number, or something complicated like a list of Charge objects).

    This is an abstract class.
    """
    # various functions can be used to convert strings into other types. each
    #  one has a name so it can be stored in the database.
    DATE = 'date'
    FLOAT = 'float'
    STRING = 'string'
    WG_CHARGES = 'wg charges'
    WG_CHARGES_WGL = 'wg charges wgl'
    PEPCO_OLD_CHARGES = 'pepco old charges'
    PEPCO_NEW_CHARGES = 'pepco new charges'
    TYPES = {
        DATE: lambda x: dateutil_parser.parse(x).date(),
        FLOAT: float,
        STRING: unicode,
        WG_CHARGES: convert_wg_charges_std,
        WG_CHARGES_WGL: convert_wg_charges_wgl,
        PEPCO_OLD_CHARGES: pep_old_convert_charges,
        PEPCO_NEW_CHARGES: pep_new_convert_charges,
    }

    __tablename__ = 'field'
    field_id = Column(Integer, primary_key=True)
    discriminator = Column(String(1000), nullable=False)

    # each Extractor subclass is associated with a Field subclass; in order
    # to get Flask-Admin to work with these classes, the relationships must
    # be defined in the subclasses (e.g. TextExtractor to TextField).
    extractor_id = Column(Integer, ForeignKey('extractor.extractor_id'))

    type = Column(Enum(*TYPES.keys(), name='field_type'))

    # string determining which Applier applies the extracted value to a UtilBill
    applier_key = Column(Enum(*Applier.KEYS.keys(), name='applier_key'))

    __table_args__ = (UniqueConstraint('extractor_id', 'applier_key'),)
    __mapper_args__ = {
        'polymorphic_on': discriminator,
        'polymorphic_identity': 'field'
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
        self._type_convert_func = self.TYPES[type]

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
        if self._value is None or input != self._input:
            self._input = input
            value_str = self._extract(input)
            try:
                value = self._type_convert_func(value_str)
            except Exception as e:
                raise ConversionError(
                    "Couldn't convert \"%s\" using function %s: %s" % (
                        value_str, self._type_convert_func, e))
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
    discriminator = Column(String(1000), nullable=False)
    name = Column(String(1000), nullable=False)

    __mapper_args__ = {
        'polymorphic_on': discriminator,
        'polymorphic_identity': 'extractor'
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

        regex = Column(String(1000), nullable=False)

        def __init__(self, *args, **kwargs):
            super(TextExtractor.TextField, self).__init__(*args, **kwargs)

        def _extract(self, text):
            m = re.search(self.regex, text)
            if m is None or len(m.groups()) != 1:
                raise MatchError(
                    'No match for pattern "%s" in text starting with "%s"' % (
                        self.regex, text[:20]))
            return m.groups()[0]

    fields = relationship(TextField, backref='extractor')

    def _prepare_input(self, utilbill, bill_file_handler):
        """Return text dumped from the given bill's PDF file.
        """
        result = utilbill.get_text(bill_file_handler)
        print result
        return result
