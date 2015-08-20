"""This file contains the most important classes related to extracting data
from utility bill files.
"""
from datetime import datetime

import re
from dateutil import parser as dateutil_parser
from flask import logging
from sqlalchemy import Column, Integer, ForeignKey, String, Enum, \
    UniqueConstraint, DateTime, func, Boolean, Float
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, object_session, MapperExtension

from core import model
from core.extraction.applier import UtilBillApplier
from core.extraction.type_conversion import \
    convert_wg_charges_wgl, pep_old_convert_charges, pep_new_convert_charges, \
    convert_address, convert_table_charges, \
    convert_wg_charges_std, convert_supplier
from core.model import BoundingBox, Address, Charge, Supplier, Session, \
    RateClass
from exc import ConversionError, ExtractionError, MatchError
from util import dateutils
from util.layout import tabulate_objects, \
    in_bounds, get_text_line, get_corner, \
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
        success_count, errors = UtilBillApplier.get_instance().apply_values(
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
    IDENTITY = 'identity'
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
        IDENTITY: lambda x: x,
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
    applier_key = Column(Enum(*UtilBillApplier.KEYS.keys(), name='applier_key'))

    # if enabled is false, then this field is skipped during extraction.
    enabled = Column(Boolean, default=True)

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
            value_output = self._extract(input)
            try:
                value = type_convert_func(value_output)
            except Exception as e:
                # don't clutter log files with huge strings
                value_str = str(value_output)
                if len(value_str) > 20:
                    value_str = value_str[:20] + '...'
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

    # A sample bill that an extractor is known to work for. Can be used for
    # debugging/testing.
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
            return Field.__table__.c.get('regex', Column(String))

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
        bounding_box_id = Column(Integer, ForeignKey(
            'bounding_box.bounding_box_id'))
        bounding_box = relationship("BoundingBox")

        # represents which corner of textboxes to consider when checking if
        # they are within a bounding box.
        # This uses the values in core.extraction.layout.CORNERS
        corner = Column(Integer)

        def __init__(self, *args, **kwargs):
            super(LayoutExtractor.BoundingBoxField, self).__init__(*args, **kwargs)
            # self.bounding_box = kwargs.get('bounding_box', None)

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
                if self.bounding_box is None:
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
                        BoundingBox.get_shifted_bbox(self.bounding_box, dx, dy),
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
            if self.multipage_table and self.maxpage:
                endpage = min(self.maxpage, len(pages))
            else:
                endpage = self.page_num

            for i in range(self.page_num-1, endpage):
                page = pages[i]

                #Either use initial bounding box for first page,
                # or use bounding box with the top y value of 'nextpage_top'
                bbox = BoundingBox.get_shifted_bbox(self.bounding_box, dx, dy)
                if i != self.page_num - 1 and self.nextpage_top:
                    bbox.y1 = self.nextpage_top + dy

                search = lambda lo: (lo.type == TEXTLINE) and \
                                    in_bounds(lo, bbox, 0)
                new_textlines = filter(search, page)

                #match regex at start of table.
                if self.table_start_regex and i == self.page_num - 1:
                    top_object = get_text_line(page,
                        self.table_start_regex)
                    if top_object:
                        new_textlines = filter(
                            lambda tl: tl.bounding_box.y1 <
                                       top_object.bounding_box.y1,
                            new_textlines)

                # if table_stop_regex matches, do not search further pages.
                if self.table_stop_regex:
                    bottom_object = get_text_line(page,
                        self.table_stop_regex)
                    if bottom_object:
                        new_textlines = filter(
                            lambda tl: tl.bounding_box.y1 >
                                       bottom_object.bounding_box.y1,
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
        if len(pages) == 0:
            raise ExtractionError("Bill has no pages.")
        dx = dy = 0
        if all(v is not None for v in
               [self.origin_regex, self.origin_x, self.origin_y]):
            #get textbox used to align the page
            alignment_obj = get_text_line(pages[0], self.origin_regex)
            if alignment_obj is not None:
                alignment_box = alignment_obj.bounding_box
                #set the bill's dx and dy so the textbox matches the expected
                # coordinates.
                dx = alignment_box.x0 - self.origin_x
                dy = alignment_box.y1 - self.origin_y
        return (pages, dx, dy)


# feel free to give this a better name
class FormatAgnosticExtractor(Extractor):
    """
    Extracts fields from the bill based on pre-existing data in the database.
    Doesn't depend on bill format, but more conservative than other
    extractors; it won't extract names (e.g. rate class names or charge
    descriptions) that it hasn't seen before.
    Therefore, it's meant to complement layout extractors / human entry,
    not 100% replace them.

    Like Layout Extractor, this relies on PDF layout information from bills.
    """
    __mapper_args__ = {'polymorphic_identity': 'formatagnosticextractor'}

    class FormatAgnosticField(Field):
        """
        A field that extracts data in a format-agnostic way, using existing
        data in the database.

        Works somewhat like a map-reduce:
        First it gets some data from the db to use as a reference.
        Then, in the 'map' step, i.e. :func:`process_textboxes` iterates
        over all textboxes in the bill and produces a set of potential,
        preliminary outputs.
        Lastly, the 'reduce', ie.e. :func:`process_results` step processes
        these
        into a final
        value.
        """
        __mapper_args__ = {'polymorphic_identity': 'formatagnosticfield'}

        def _extract(self, input):
            bill, pages = input
            db_data = self.load_db_data(bill)
            map_results = self.process_textboxes(pages, db_data)
            possible_values = self.process_results(map_results)
            return possible_values

        def load_db_data(self, utilbill):
            """
            Load relevant data from the database, e.g. a list of existing
            rate class names.
            """
            raise NotImplementedError

        def process_textboxes(self, pages, db_data):
            """
            Iterate over textboxes and return a list of preliminary results.
            """
            raise NotImplementedError

        def process_results(self, map_results):
            """
            Take output from process_textboxes, and process them into a final value.
            """
            raise NotImplementedError

    # feel free to rename
    class ChargeGobbler(FormatAgnosticField):
        """
        Finds and processes charges on a given bill.
        This field searches for all text boxes on a bill that match an
        existing charge name.
        If one is found, the charge rate and value are captured by looking at
        textboxes on the same row.
        This works under the assumption that charges are stored in a table
        format, with charge names on the left and charge values on the right.
        This assumption doesn't always hold true (e.g. some bills have the charge
        name and value in the same textbox, and multiple charges on the same
        horizontal line). When this is the case the field acts conservatively,
        and simply ignores those textboxes.

        This field doesn't find *all* charges for a bill, but works for almost
        any format, and captures supply charges that are often not found in a
        single, predictable region on the page, so in some cases this is more
        effective than a layout extractor.
        Thus, this could be a good preliminary tool for populating the database
        with charges of bills, before using layout extractors and human review.
        """
        __mapper_args__ = {'polymorphic_identity': 'chargegobbler'}

        def __init__(self, *args, **kwargs):
            """
            This field's type is always TABLE_CHARGES, this field's applier
            key is always CHARGES
            """
            super(Field, self).__init__(
                applier_key=UtilBillApplier.CHARGES, type=Field.TABLE_CHARGES,
                *args, **kwargs)

        def load_db_data(self, utilbill):
            """ Get charge names from the database
            """
            s = Session()
            q = s.query(Charge.description, Charge.rsi_binding).filter(
                (Charge.description != 'New Charge - Insert description here') &
                (Charge.description != '')).distinct()
            charge_results = q.all()
            return charge_results

        def process_textboxes(self, pages, charge_results):
            """
            Finds table rows corresponding to charges in a bill.
            Takes a list of text boxes and a list of existing charges as input.
            :param charge_results: A list of SQLAlchemy results, with teh
                    fields Charge.description and Charge.rsi_binding.
            :return: A 2d array of strings, as input for
            :func:`convert_table_charges`
            """
            charge_rows = []
            for p in pages:
                obj_index = 0
                while obj_index < len(p):
                    obj = p[obj_index]
                    sanitized_textline = Charge.description_to_rsi_binding(obj.text)
                    if not sanitized_textline:
                        obj_index += 1
                        continue

                    matching_charge = None
                    for c in charge_results:
                        sanitized_charge_name = Charge.description_to_rsi_binding(
                            c.description)
                        if sanitized_textline == sanitized_charge_name:
                            matching_charge = c
                            break
                    if matching_charge is None:
                        obj_index += 1
                        continue

                    # get whole row to the right of current box
                    row = [obj.text.strip()]
                    obj_index += 1
                    while obj_index < len(p) and p[obj_index].bounding_box.y0 == \
                            obj.bounding_box.y0:
                        row.append(p[obj_index].text.strip())
                        obj_index += 1
                    # ignore rows with only one piece of text, as they are most
                    # likely not charges.
                    if len(row) > 1:
                        charge_rows.append(row)
            return charge_rows

        def process_results(self, charge_rows):
            """
            In this case, we don't have to do anything before return this and
            passing it onto the type conversion function.
            :return: its input, unmodified
            """
            return charge_rows

    class RateClassGobbler(FormatAgnosticField):
        """
        Field that looks for pieces of text in a bill that matches an existing
        rate class. The rate classes for the bill's utility are loaded, and are
        normalized to a standard name to account for formatting differences in
        the database. Then, for any piece of text that matches an existing rate
        class name, the corresponding rate class is returned.

        If only one rate class is found, it is returned. Otherwise an error
        is raised. Note that some bills can have multiple rate classes,
        e.g. BGE which has both gas and eletric services in one bill.
        """

        __mapper_args__ = {'polymorphic_identity': 'rateclassgobbler'}

        def __init__(self, *args, **kwargs):
            """
            This field's type is always IDENTITY,
            this field's applier key is always RATE_CLASS
            """
            super(Field, self).__init__(applier_key =UtilBillApplier.RATE_CLASS,
                                        type=Field.IDENTITY, *args, **kwargs)

        def load_db_data(self, utilbill):
            """
            Loads rate classes from the database that have the same utility
            as utilbill.
            Rate classes are grouped by normalized name to account for minor
            changes in formatting in the database.
            :return: A map {<normalized rate class name> : <representative rate
            class> }
            """
            s = Session()
            q = s.query(RateClass).filter(RateClass.utility_id ==
                                          utilbill.utility_id)
            rate_classes = q.all()

            # group rate classes by normalized name
            rc_map = {self.normalize_text(rc.name): rc for rc in rate_classes}
            return rc_map

        def process_textboxes(self, pages, rc_map):
            """
            For each textbox that has the same text as an existing rate class
            name, return the corresponding rate class.
            :param pages: The layout elements of the bill
            :param rc_map: A map of normalized rate class name to RateClass
            object.
            :return: A set of rate classes, unique up to normalized name,
            found in the bill.
            """
            matching_rate_classes = {}
            if len(rc_map.keys()) == 0:
                return []
            for p in pages:
                for obj in p:
                    sanitized_textline = self.sanitize_rate_class_name(obj.text)
                    normalized_textline = self.normalize_text(
                        sanitized_textline)
                    if not normalized_textline:
                        continue

                    for norm_name, rc in rc_map.iteritems():
                        if normalized_textline == norm_name:
                            matching_rate_classes[norm_name]= rc
                            break
            return matching_rate_classes.values()

        def process_results(self, rate_classes):
            """
            Takes a list of rate classes. If exactly one rate class is found,
            it is returned. Otherwise, an error is raised.
            :param rate_class_map: A list of rate classes.
            :return:
            """
            if len(rate_classes) == 1:
                return  rate_classes[0]
            elif len(rate_classes) == 0:
                raise ExtractionError("No rate classes found in this bill.")
            else:
                raise ExtractionError("Multiple rate classes found: %s") % \
                      rate_classes

        @classmethod
        def sanitize_rate_class_name(cls, text):
            """
            Removes some common prefixes / suffixes that are often attached
            to rate class names.
            :param text: Text containing a rate class name
            :return: The rate class name contained in text.
            """
            # e.g. 'rate class: residential'
            text = re.sub("^rate(?: class)?:\s*", "", text, flags=re.IGNORECASE)
            # e.g. 'rate class: non-residential service number 12345'
            text = re.sub("service number[\d\s]+", "", text, flags=re.IGNORECASE)
            return text

        @staticmethod
        def normalize_text(text):
            """
            NOTE: Currently only used by RateClassGobbler, but this is a
            pretty generic method that could be moved somewhere else.

            Normalizes text by removing non-alphanumeric characters and replacing
            them with underscores. Trailing and leading non-alphanumeric characters
            are removed.
            """
            text = text.upper()
            text = re.sub(r'[^A-Z0-9]', ' ', text)
            text = text.strip().lstrip()
            return re.sub(r'\s+', '_', text)

    class BillPeriodGobbler(FormatAgnosticField):
        """
        A function that attempts to get the billing period of a bill.
        1. First, all dates on the bill are loaded, and their location stored.
        2. Then, pairs of dates that are roughly one month apart are grouped as
         potential start and end dates.
        3. The start and end dates that are geometrically closest (usually in the
         same textbox, so a distance of 0) are then chosen as the most likely
         bill period.
         *** (Note: the x distance is weighted less than the y distance,
         since pieces of text on the same line are more likely to be related than
         pieces of text that are vertically aligned but on different lines.
        4. It's possible for a bill (e.g. for BGE, with both gas and electric
         services) to have multiple periods on it, so an array of possibly
         periods is returned.
        :param bill: The bill to be analyzed
        :return: A list of possible bill periods. Each bill period is a tuple (
        start_date, end_date, distance), where distance is the geometrical
        distance on the bill's page.
        """

        __mapper_args__ = {'polymorphic_identity': 'billperiodgobbler'}

        date_long_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
        date_mm_dd_yy_format = r'\d{2}\/\d{2}\/\d{2,4}'

        def __init__(self, *args, **kwargs):
            """
            This field's type is always IDENTITY
            """

            # TODO self.applier_key = 'bill period'
            # not a valid applier key, since this field does both period
            # start and period end. Need to find a better way to fit
            # FormatAgnosticExtractor into the structure of extractor.

            super(Field, self).__init__(type=Field.IDENTITY, *args, **kwargs)

        def load_db_data(self, utilbill):
            """
            This field doesn't use data from the database.
            """
            return None

        def process_textboxes(self, pages, db_data):
            """
            Gets all dates on the bill and their position.
            :return: a list of {'date':<date>, 'obj':<layout_element>}
            """
            dates = []
            for p in pages:
                for obj in p:
                    matches = re.findall(self.date_long_format, obj.text)
                    matches += re.findall(self.date_mm_dd_yy_format, obj.text)
                    for s in matches:
                        date = dateutils.parse_date(s)
                        # store obj to keep track of page number, x, y
                        date_obj = {'date': date, 'obj': obj }
                        dates.append(date_obj)
            dates = sorted(dates, key=lambda do: do['date'])
            return dates

        def process_results(self, date_objs):
            """
            Given a set of date objects from a bill,
            :param date_objs: A list of {'date':<date>, 'obj':<layout_element>}
            :return: A pair (start_date, end_date) or throws an error if
            multiple / no periods are found.
            """
            # Find potential ~1 month periods
            periods = []
            for idx, start_obj in enumerate(date_objs):
                for end_obj in date_objs[idx+1:]:
                    # skip if dates are on a different page
                    if start_obj['obj'].page_num != end_obj['obj'].page_num:
                        continue
                    # bill period length must be in [20, 40]
                    if (end_obj['date'] - start_obj['date']).days < 20:
                        continue
                    if (end_obj['date'] - start_obj['date']).days > 40:
                        break
                    # get geometric (manhattan) distance of text boxes
                    dx = abs(start_obj['obj'].bounding_box.x0 -
                             end_obj['obj'].bounding_box.x0)
                    dy = abs(start_obj['obj'].bounding_box.y1 -
                             end_obj['obj'].bounding_box.y1)
                    # x distance is less improtant than y - pieces of text on
                    # different lines are less likely to be related.
                    distance = 0.25 * dx + 1.0 * dy
                    periods.append((start_obj['date'], end_obj['date'], distance))

            # sort by geometric distance on bill, after removing duplicate values
            periods = sorted(set(periods), key=lambda p: p[2])
            # get only the pairs of dates that are closest to each other on the page
            likeliest_periods = filter(lambda p: p[2] == periods[0][2], periods)

            if len(likeliest_periods) == 1:
                p = likeliest_periods[0]
                return (p[0], p[1])
            elif len(likeliest_periods) == 0:
                raise ExtractionError("No potential bill periods found in this "
                                      "bill.")
            else:
                raise ExtractionError("Multiple potential bill periods found: %s") % likeliest_periods

    def __init__(self):
        self.rate_class_field = FormatAgnosticExtractor.RateClassGobbler(
            enabled=True)
        self.charges_field = FormatAgnosticExtractor.ChargeGobbler(enabled=True)
        self.bill_period_field = FormatAgnosticExtractor.BillPeriodGobbler(
            enabled=True)

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
        # TODO this code is highly repetitive, since bill_period_gobbler
        # returns both start and end at once. Need to refactor to make more
        # general, or ideally refactor so we don't have to override
        # Extractor.get_values
        if self.rate_class_field.enabled is not False:
            try:
                rate_class_value = self.rate_class_field.get_value(self._input)
            except ExtractionError as error:
                errors[self.rate_class_field.applier_key] = error
            else:
                good[self.rate_class_field.applier_key] = rate_class_value
        if self.charges_field.enabled is not False:
            try:
                charges_value = self.charges_field.get_value(self._input)
            except ExtractionError as error:
                errors[self.charges_field.applier_key] = error
            else:
                good[self.charges_field.applier_key] = charges_value
        if self.bill_period_field.enabled is not None:
            try:
                bill_period = self.bill_period_field.get_value(self._input)
            except ExtractionError as error:
                errors[UtilBillApplier.START] = error
                errors[UtilBillApplier.END] = error
            else:
                good[UtilBillApplier.START] = bill_period[0]
                good[UtilBillApplier.END] = bill_period[1]

        return good, errors


    def _prepare_input(self, utilbill, bill_file_handler):
        """
        Prepares input for format-agnostic extractor extractor by getting PDF
        text objects and keeping track of the utility bill itself, to use for
        database queries in the fields.
        """
        pages = utilbill.get_layout(bill_file_handler, PDFUtil())
        pages = [filter(lambda o: o.type == TEXTLINE, p) for p in pages]
        # check if bill has no text
        if len(pages) == 0:
            raise ExtractionError("Bill has no pages.")
        if sum(len(p) for p in pages) == 0:
            raise ExtractionError("Bill has no text.")
        return (utilbill, pages)


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
    field_total = Column(Integer)
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
    total_by_month = Column(HSTORE)
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
    if applier_key == UtilBillApplier.RATE_CLASS:
        subregex = r"[\s\-_]+"
        exc_string = re.sub(subregex, "_", extracted_value.lower().strip())
        exc_string = re.sub(r"pepco_", "", exc_string)
        db_string = re.sub(subregex, "_", db_value.name.lower().strip())
    elif applier_key == UtilBillApplier.BILLING_ADDRESS or applier_key == \
            UtilBillApplier.SERVICE_ADDRESS:
        # get fields of address, and remove empty ones
        exc_fields = filter(None, (extracted_value.addressee,
                     extracted_value.street, extracted_value.city,
            extracted_value.state))
        exc_string = " ".join(exc_fields)
        exc_string = exc_string.upper()


        # get fields of address, and remove empty ones
        db_fields = filter(None, (db_value.addressee,
                     db_value.street, db_value.city, db_value.state))
        db_string = " ".join(db_fields)
        db_string = db_string.upper()
    else:
        # don't strip extracted value, so we can catch extra whitespace
        exc_string = str(extracted_value)
        db_string = str(db_value).strip()
    return exc_string == db_string

def serialize_field(result):
    """
    Converts a field into a json-serializable type, such as an int, string,
    or dictionary.
    When given a list, the members of the list are serialized.
    If no proper conversion can be found, then str(results) is returned.
    """
    if result is None:
        return None;
    if isinstance(result, list):
        return map(serialize_field, result)
    if isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, Address):
        return {
            'addressee': result.addressee,
            'street': result.street,
            'city': result.city,
            'state': result.state,
            'postal_code': result.postal_code,
        }
    if isinstance(result, Charge):
        return {
            'description': result.description,
            'quantity': result.quantity,
            'unit': result.unit,
            'rate': result.rate,
            'target_total': result.target_total,
        }
    if isinstance(result, Supplier):
        return {'name': result.name}
    return str(result)