"""This file contains the most important classes related to extracting data
from utility bill files.
"""
from datetime import datetime
import re

from dateutil import parser as dateutil_parser
from flask import logging
from sqlalchemy import Column, Integer, ForeignKey, String, Enum, \
    UniqueConstraint, DateTime, func, Boolean, Float, CheckConstraint
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, object_session, MapperExtension

from core import model
from core.extraction.applier import Applier
from core.extraction.type_conversion import \
    convert_wg_charges_wgl, pep_old_convert_charges, pep_new_convert_charges, \
    convert_address, convert_table_charges, \
    convert_wg_charges_std, convert_supplier
from core.model import LayoutElement
from exc import ConversionError, ExtractionError, ApplicationError, MatchError
from util.layout import tabulate_objects, BoundingBox, \
    group_layout_elements_by_page, in_bounds, get_text_line, get_corner, \
    get_text_from_bounding_box, TEXTLINE
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
        success_count, errors = Applier.get_instance().apply_values(
            best_extractor, utilbill, self._bill_file_handler)
        utilbill.date_extracted = datetime.utcnow()
        error_list_str = '\n'.join(('Field "%s": %s: %s' % (
            key, exception.__class__.__name__, exception.message)) for
                                   (key, exception) in errors.iteritems())
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
    ADDRESS = 'address'
    DATE = 'date'
    FLOAT = 'float'
    STRING = 'string'
    SUPPLIER = 'supplier'
    TABLE_CHARGES = 'table charges'
    WG_CHARGES = 'wg charges'
    WG_CHARGES_WGL = 'wg charges wgl'
    PEPCO_OLD_CHARGES = 'pepco old charges'
    PEPCO_NEW_CHARGES = 'pepco new charges'
    TYPES = {
        ADDRESS: convert_address,
        DATE: lambda x: dateutil_parser.parse(x).date(),
        FLOAT: lambda x: float(x.replace(',','')),
        STRING: unicode,
        SUPPLIER: convert_supplier,
        TABLE_CHARGES: convert_table_charges,
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
        ForeignKey('utilbill.id'))
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

    def get_values(self, utilbill, bill_file_handler):
        """
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler
        :return: dictionary of applier key -> extracted value for fields that
        succeeded in extracted values, and dictionary of applier key ->
        ExtractionError for fields that failed.
        """
        self._input = self._prepare_input(utilbill, bill_file_handler)
        good, errors = {}, {}
        for field in self.fields:
            # still extract data if field.enabled is None
            if field.enabled is False:
                continue
            try:
                value = field.get_value(self._input)
            except ExtractionError as error:
                errors[field.applier_key] = error
            else:
                good[field.applier_key] = value
        return good, errors

    def get_success_count(self, utilbill, bill_file_handler):
        """
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler
        :return: number of fields that could be extracted (int)
        """
        good, _ = self.get_values(utilbill, bill_file_handler)
        return len(good)


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


class LayoutExtractor(Extractor):
    """
    Extracts data about a bill based on the layout of text in the PDF
    """
    __mapper_args__ = {'polymorphic_identity': 'layoutextractor'}

    #used to align bills of the same format that are shifted slightly:
    #A regular expression used to match a text box used to align the bill.
    origin_regex = Column(String)
    # The coordinates that the layout object should have, if the bill is aligned
    origin_x = Column(Float)
    origin_y = Column(Float)

    class BoundingBoxField(Field):
        """
        A field that extracts text that is within a given bounding box on the PDF.

        """
        __mapper_args__ = {'polymorphic_identity': 'boundingboxfield'}

        # First page is numbered 1, not 0
        # The first (or only) page to search for
        page_num = Column(Integer)
        # The last page to search for. If maxpage is None, then only page_num
        #  is used.
        maxpage = Column(Integer)
        # regex to apply to text after it has been recovered.
        # If bounding box is null, then the first textline matching bbregex
        # is returned from the page.
        bbregex = Column(String)
        # If not null, offset_regex is used to find a text object that served
        #  as the origin for the bounding box. This is used when a certain
        # region on a bill has different locations on different PDFs, but the
        #  same content.
        offset_regex = Column(String)

        # bounding box coordinates.
        # If these are None, then the first textbox that matches the bbregex
        # is used.
        bbminx = Column(Float)
        bbminy = Column(Float)
        bbmaxx = Column(Float)
        bbmaxy = Column(Float)

        # represents which corner of textboxes to consider when checking if
        # they are within a bounding box.
        # This uses the values in core.extraction.layout.CORNERS
        corner = Column(Integer)

        def __init__(self, *args, **kwargs):
            super(LayoutExtractor.BoundingBoxField, self).__init__(*args, **kwargs)

        def _extract(self, layoutdata):
            (pages, dx, dy) = layoutdata
            if self.page_num > len(pages):
                raise ExtractionError('Not enough pages. Could not get page '
                                      '%d out of %d.' % (self.page_num,
                len(pages)))
            if self.maxpage:
                endpage = min(self.maxpage, len(pages))
            else:
                endpage = self.page_num

            text=""
            for page in pages[self.page_num-1:endpage]:
                #if bounding box is None, instead of using geometry, return first
                # text line object that matches bbregex.
                if any(x is None for x in [self.bbminx, self.bbminy, self.bbmaxx,
                    self.bbmaxy]):
                    textline = get_text_line(page,
                        self.bbregex)
                    if textline is None:
                        continue
                    text = textline.text
                else:
                    #if offset_regex is not None, then find the first block of
                    # text that it matches, and use that as the origin for
                    # the bounding box's coordiantes.
                    if self.offset_regex:
                        textline = get_text_line(page, self.offset_regex)
                        if textline is None:
                            continue
                        offset_x, offset_y = get_corner(textline,
                            self.corner)
                        dx = offset_x
                        dy = offset_y
                    text = get_text_from_bounding_box(page,
                        BoundingBox(minx=self.bbminx + dx, miny=self.bbminy + dy,
                            maxx=self.bbmaxx + dx, maxy=self.bbmaxy + dy),
                        self.corner)
                #exit on first match found
                if text:
                    break

            if self.bbregex:
                m = re.search(self.bbregex, text, re.IGNORECASE | re.DOTALL |
                                                 re.MULTILINE)
                if m is None:
                    raise MatchError(
                        'No match for pattern "%s" in text starting with "%s"' % (
                            self.bbregex, text[:20]))
                text = "\n".join(m.groups())

            # this is done after regex matching, in case a capture group
            # matches an empty string
            text = text.strip()
            if not text:
                raise ExtractionError('No text found.')
            return text

    class TableField(BoundingBoxField):
        """
        A field that represents tabular data, within a given bounding box.

        For multi-page tables, in addition to the initial bounding box,
        one specifies a max page number and top margin for the
        subsequent pages. One can also specifiy a regex to find a text object
        that marks the end or start of the table (inclusive).
        """
        __mapper_args__ = {'polymorphic_identity': 'tablefield'}

        # Optional regexes that match text objects that delimit the vertical
        # start and end of the table. (in addition to limiting text within the
        # bounding box). The matched text is not part of the table.
        # Vertical boundaries are used rather than horizontal because tables
        # often move up and down between different bills but tend not to move
        # horizontally.
        table_start_regex = Column(String)
        table_stop_regex = Column(String)

        # whether this table extends across multiple pages.
        multipage_table = Column(Boolean)
        # For multi-page tables, the y-value at which the table starts,
        # on subsequent pages. i.e. the top margin.
        nextpage_top = Column(Float)

        def __init__(self, *args, **kwargs):
            super(LayoutExtractor.BoundingBoxField, self).__init__(
                *args, **kwargs)

        def _extract(self, layoutdata):
            pages, dx, dy = layoutdata
            if self.page_num > len(pages):
                raise ExtractionError('Not enough pages. Could not get page '
                                      '%d out of %d.' % (self.page_num,
                len(pages)))

            table_data = []

            #determine last page to search
            if self.multipage_table:
                endpage = min(self.maxpage, len(pages))
            else:
                endpage = self.page_num

            for i in range(self.page_num-1, endpage):
                page = pages[i]

                #Either use initial bounding box for first page,
                # or use bounding box with the top y value of 'nextpage_top'
                if i == self.page_num - 1:
                    bbox = BoundingBox(
                            minx=self.bbminx + dx,
                            miny=self.bbminy + dy,
                            maxx=self.bbmaxx + dx,
                            maxy=self.bbmaxy + dy)
                else:
                    bbox = BoundingBox(
                            minx = self.bbminx + dx,
                            miny = self.bbminy + dy,
                            maxx = self.bbmaxx + dx,
                            maxy = self.nextpage_top + dy)

                search = lambda lo: (lo.type == TEXTLINE) and \
                                    in_bounds(lo, bbox, 0)
                new_textlines = filter(search, page)

                #match regex at start of table.
                if self.table_start_regex and i == self.page_num - 1:
                    top_object = get_text_line(page,
                        self.table_start_regex)
                    if top_object:
                        new_textlines = filter(
                            lambda tl: tl.y0 < top_object.y0,
                            new_textlines)

                # if table_stop_regex matches, do not search further pages.
                if self.table_stop_regex:
                    bottom_object = get_text_line(page,
                        self.table_stop_regex)
                    if bottom_object:
                        new_textlines = filter(
                            lambda tl: tl.y0 > bottom_object.y0,
                            new_textlines)
                        table_data.extend(tabulate_objects(new_textlines))
                        break

                table_data.extend(tabulate_objects(new_textlines))

            # extract text from each table cell
            output_values = []
            for row in table_data:
                out_row = [tl.text.strip() for tl in
                    row]
                #remove empty cells
                out_row = filter(bool, out_row)
                if out_row:
                    output_values.append(out_row)

            if not output_values:
                raise ExtractionError("No values found in table.")
            return output_values

    def _prepare_input(self, utilbill, bill_file_handler):
        """
        Prepares input for layout extractor by getting PDF layout data
        and checking if bill's PDF is misaligned.
        """
        pages = utilbill.get_layout(bill_file_handler, PDFUtil())
        dx = dy = 0
        if all(v is not None for v in
               [self.origin_regex, self.origin_x, self.origin_y]):
            #get textbox used to align the page
            alignment_box = get_text_line(pages[0], self.origin_regex)
            if alignment_box is not None:
                #set the bill's dx and dy so the textbox matches the expected
                # coordinates.
                dx = alignment_box.x0 - self.origin_x
                dy = alignment_box.y0 - self.origin_y
        return (pages, dx, dy)


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
    field_period_total = Column(Integer)
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
    period_total_by_month = Column(HSTORE)
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
            date_count_dict = {str(date): str(counts['fields'].get(field_name,
                0)) for date, counts in metadata['dates'].iteritems()}
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