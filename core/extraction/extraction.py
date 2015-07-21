"""This file contains the most important classes related to extracting data
from utility bill files.
"""
from datetime import datetime
import re

from dateutil import parser as dateutil_parser
from flask import logging
from sqlalchemy import Column, Integer, ForeignKey, String, Enum, \
    UniqueConstraint, DateTime, func, Float, Boolean
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, object_session, MapperExtension

from core import model
from core.extraction.applier import Applier
from core.extraction.type_conversion import \
    convert_wg_charges_wgl, pep_old_convert_charges, pep_new_convert_charges, \
    convert_wg_charges_std
from exc import ConversionError, ExtractionError, ApplicationError, MatchError
from util.pdf import PDFUtil

__all__ = [
    'Main',
    'Extractor',
    'Field',
    'TextExtractor',
    'ExtractorResult'
]


class Main(object):
    """Handles everything about the extraction process for a particular bill.
    Consumers only need to use this.
    """
    def __init__(self, bill_file_handler):
        self._bill_file_handler = bill_file_handler
        self.log = logging.getLogger()

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
        success_count, errors = best_extractor.apply_values(
            utilbill, self._bill_file_handler, Applier.get_instance())
        utilbill.date_extracted = datetime.utcnow()
        error_list_str = '\n'.join(('Field "%s": %s: %s' % (
            key, exception.__class__.__name__, exception.message)) for
                                   (key, exception) in errors)
        self.log.info(
            'Applied extractor %(eid)s "%(ename)s" to bill %(bid)s from %('
            'utility)s %(start)s - %(end)s received %(received)s: '
            '%(success)s/%(total)s fields\n%(errors)s' % dict(
                eid=best_extractor.extractor_id, ename=best_extractor.name,
                utility=utilbill.get_utility_name(), bid=utilbill.id,
                start=utilbill.period_start, end=utilbill.period_end,
                received=utilbill.date_received, success=success_count,
                total=success_count + len(errors), errors=error_list_str))

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
            if object_session(instance).is_modified(
                    instance, include_collections=False):
                instance.extractor.modified = datetime.utcnow()

        def before_delete(self, mapper, connection, instance):
            instance.extractor.modified = datetime.utcnow()

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

    # if enabled is false, then this field is skipped during extraction.
    enabled = Column(Boolean, default=True, nullable=False)

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
    representative_bill_id = Column(Integer,
        ForeignKey('utilbill.id'), nullable=False)
    representative_bill = relationship('UtilBill')
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
        :return: list of (applier key, extracted value) pairs for fields that
        succeeded in extracted values, and list of (applier key,
        ExtractionError) pairs for fields that failed.
        """
        self._input = self._prepare_input(utilbill, bill_file_handler)
        good, errors = [], []
        for field in self.fields:
            # still extract data run if field.enabled is None
            if field.enabled is False:
                continue
            try:
                value = field.get_value(self._input)
            except ExtractionError as error:
                errors.append((field.applier_key, error))
            else:
                good.append((field.applier_key, value))
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

        # hack to force field values to be applied in the order of Applier.KEYS,
        # because of dependency of some values on others.
        # TODO: probably Applier should get a whole Extractor passed to it
        # and apply all the fields, so it can ensure they get applied in the
        # right order. extraction results should not be ordered anyway.
        good = sorted(good, key=(
            lambda (applier_key, _): applier.get_keys().index(applier_key)))

        for applier_key, value in good:
            try:
                applier.apply(applier_key, value, utilbill)
            except ApplicationError as error:
                errors.append((applier_key, error))
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

        def     __init__(self, *args, **kwargs):
            super(TextExtractor.TextField, self).__init__(*args, **kwargs)

        def _extract(self, text):
            # TODO: DOTALL should not be used because there is no way to
            # match any character except newlines
            m = re.search(self.regex, text,
                          re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if m is None:
                raise MatchError(
                    'No match for pattern "%s" in text starting with "%s"' % (
                        self.regex, text.strip()[:20]))
            # In case of a | in the regex, in which there are multiple
            # capture groups, remove the matches which are None
            # e.g. r'(either this)|(or this)'
            match_groups = filter(None, m.groups())
            if len(match_groups) != 1:
                raise MatchError('Found %d matches for pattern "%s" in text '
                                 'starting with "%s"' % (len(match_groups),
                self.regex, text.strip()[:20]))
            return match_groups[0]

    #fields = relationship(TextField, backref='extractor')

    def _prepare_input(self, utilbill, bill_file_handler):
        """Return text dumped from the given bill's PDF file.
        """
        return utilbill.get_text(bill_file_handler, PDFUtil())


class ExtractorResult(model.Base):
    __tablename__ = 'extractor_result'

    extractor_result_id = Column(Integer, primary_key=True)
    extractor_id = Column(Integer, ForeignKey('extractor.extractor_id'))

    # id of task in celery
    task_id = Column(String, nullable=False)
    # id of task group in celery, used to get individual sub-tasks
    parent_id = Column(String, nullable=False)
    # when the task was started and finished
    started = Column(DateTime, nullable=False)
    finished = Column(DateTime)
    # used when filtering bills by utility
    utility_id = Column(Integer, ForeignKey('utility.id'))
    # total bills to run in the task
    bills_to_run = Column(Integer, nullable=False)

    # results to be filled in after the test has finished
    # num. of bills with all fields enterred
    all_count = Column(Integer)
    # num. of bills with any fields enterred
    any_count = Column(Integer)
    # total number of bills run so far
    total_count = Column(Integer)
    # number of bills that have been processed in the database, and had at
    # least one field extracted.
    verified_count = Column(Integer)

    #TODO should find a way to sync these with UtilBill's list of fields
    # total counts for each field
    field_billing_address = Column(Integer)
    field_charges = Column(Integer)
    field_end = Column(Integer)
    field_energy = Column(Integer)
    field_next_read = Column(Integer)
    field_rate_class = Column(Integer)
    field_start = Column(Integer)
    field_service_address = Column(Integer)

    # accuracy of results when compared to fields in the database.
    field_billing_address_fraction = Column(Float)
    field_charges_fraction = Column(Float)
    field_end_fraction = Column(Float)
    field_energy_fraction = Column(Float)
    field_next_read_fraction = Column(Float)
    field_rate_class_fraction = Column(Float)
    field_start_fraction = Column(Float)
    field_service_address_fraction = Column(Float)

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
        self.verified_count = metadata['verified_count']

        # update overall count and count by month for each field
        for field_name in metadata['fields'].keys():
            attr_name = field_name.replace(" ", "_")
            count_for_field = metadata['fields'][field_name]
            setattr(self, "field_" + attr_name, count_for_field)
            correct_fraction = metadata['fields_fraction'][field_name]
            setattr(self, "field_"+attr_name+"_fraction", correct_fraction)
            date_count_dict = {str(date): str(counts.get(field_name, 0)) for
                               date, counts in metadata['dates'].iteritems()}
            setattr(self, attr_name + "_by_month", date_count_dict)


def verify_field(applier_key, extracted_value, db_value):
    """
    Compares an extracted value of a field to the corresponding value in the
    database
    :param applier_key: The applier key of the field
    :param extracted_value: The value extracted from the PDF
    :param db_value: The value already in the database
    :return: Whether these values match.
    """
    if applier_key == Applier.RATE_CLASS:
        subregex = r"[\s\-_]+"
        exc_string = re.sub(subregex, "_", extracted_value.lower().strip())
        exc_string = re.sub(r"pepco_", "", exc_string)
        db_string = re.sub(subregex, "_", db_value.name.lower().strip())
    else:
        # don't strip extracted value, so we can catch extra whitespace
        exc_string = str(extracted_value)
        db_string = str(db_value).strip()
    return exc_string == db_string