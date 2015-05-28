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
            # method
            method_name = attr.__name__
            method = getattr(utilbill, method_name)
            apply = lambda: method(value)
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


def convert_wg_charges(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_name_map = Session().query(Utility).filter_by(
        name='Washington Gas').one().charge_name_map

    groups = '.*DISTRIBUTION SERVICE(.*)NATURAL GAS SUPPLY SERVICE(.*)TAXES(.*)'
    num = r'[\d.]*'
    charge_total = r'\$\s*' + num
    charge_stuff = (r'\s*' + num + r'\s*(?:TH\s*)?(?:@\s*' + num
                    + ')?(?:x\s*)?' + num + r'\s*' + charge_total + r'\s*')
    charge_name = r'[A-Za-z- -]+'
    charge = r'\s*(' + charge_name + charge_stuff + r')\s*'

    d_charges, s_charges, tax_charges = re.match(groups, text).groups()

    d_charge_strs = re.findall(charge, d_charges)
    s_charge_strs = re.findall(charge, s_charges)
    tax_charge_strs = re.findall(charge, tax_charges)

    def extract_charge(charge_str, charge_type):
        name = re.match(charge_name, charge_str).group(0).strip()
        # "*?" means non-greedy *
        total_str = re.match(r'.*?(' + num + r')\s*$', charge_str).group(1)
        rsi_binding = charge_name_map.get(name, name.replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(total_str),
                      type=charge_type)

    charges = []
    for charge_type, charge_texts in [(Charge.DISTRIBUTION, d_charge_strs),
                                      (Charge.SUPPLY, s_charge_strs),
                                      (Charge.DISTRIBUTION, tax_charge_strs)]:
        charges.extend([extract_charge(t, charge_type) for t in charge_texts])
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
    TYPES = {
        DATE: lambda x: dateutil_parser.parse(x).date(),
        FLOAT: float,
        STRING: unicode,
        WG_CHARGES: convert_wg_charges,
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
    applier_key = Column(Enum(*Applier.KEYS.keys(), name='applier_key'),
                         unique=True)

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
    discriminator = Column(String, nullable=False)
    name = Column(String, nullable=False)

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

        regex = Column(String, nullable=False)

        def __init__(self, *args, **kwargs):
            super(TextExtractor.TextField, self).__init__(*args, **kwargs)

        def _extract(self, text):
            m = re.match(self.regex, text)
            if m is None or len(m.groups()) != 1:
                raise MatchError(
                    'No match for pattern "%s" in text starting with "%s"' % (
                        self.regex, text[:20]))
            return m.groups()[0]

    fields = relationship(TextField, backref='extractor')

    def _prepare_input(self, utilbill, bill_file_handler):
        """Return text dumped from the given bill's PDF file.
        """
        return utilbill.get_text(bill_file_handler)

