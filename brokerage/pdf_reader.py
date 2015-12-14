"""Code related to getting quotes out of PDF files.
"""
import re
from pdfminer.layout import LTTextBox
from brokerage.reader import Reader
from core.exceptions import ValidationError
from util.pdf import PDFUtil


class PDFReader(Reader):
    """Implementation of Reader for extracting tabular data from PDFs.
    """
    # positions: these can be used as arguments to get to choose which part
    # of an element the coordinates apply to
    LOWER_LEFT = object()
    CENTER = object()

    @classmethod
    def distance(cls, element, x, y, position):
        """Return distance of a PDF element from the given coordinates.
        :param element: any PDF element
        :param position: a constant specifying which point on the element
        (e.g. lower left corner) should be used for element coordinates
        :return: float
        """
        if position is cls.LOWER_LEFT:
            element_x, element_y = element.x0, element.y0
        elif position is cls.CENTER:
            element_x = (element.x0 + element.x1) / 2.
            element_y = (element.y0 + element.y1) / 2.
        else:
            # add more positions if needed
            raise ValueError('Unknown position: %s' % x)
        return ((element_x - x) ** 2 + (element_y - y) ** 2)**.5

    def __init__(self, offset_x=0, offset_y=0, tolerance=30):
        """
        :param offset_x: float to add to all x coordinates when getting
        data from the PDF file.
        :param offset_y: float to add to all y coordinates when getting
        data from the PDF file.
        :param tolerance: max allowable distance between expected and actual
        coordinates of elements in the PDF.
        """
        self.offset_x = offset_x
        self.offset_y = offset_y
        self._tolerance = tolerance
        self._pages = None

    def load_file(self, quote_file):
        """Read from 'quote_file'.
        :param quote_file: file to read from.
        """
        self._pages = PDFUtil().get_pdfminer_layout(quote_file)

    def is_loaded(self):
        return self._pages != None

    def _get_page(self, page_number):
        try:
            return self._pages[page_number - 1]
        except IndexError:
            raise ValidationError('No page %s: last page number is %s' % (
                page_number, len(self._pages)))

    def get(self, page_number, y, x, the_type):
        """
        Extract a value from the text box in the PDF file whose upper left
        corner is closest to the given coordinates, within some tolerance.

        :param page_number: PDF page number starting with 1.
        :param y: vertical coordinate (starting from bottom)
        :param x: horizontal coordinate (starting from left)
        :param the_type: ignored. all values are strings.

        :return: text box content (string), with whitespace stripped
        """
        y += self.offset_y
        x += self.offset_x

        # get all text boxes on the page (there must be at least one)
        page = self._get_page(page_number)
        text_boxes = list(
            element for element in page if isinstance(element, LTTextBox))
        if text_boxes == []:
            raise ValidationError('No text elements on page %s' % page_number)

        # find closest box to the given coordinates, within tolerance
        closest_box = min(text_boxes, key=lambda box: self.distance(
            box, x, y, self.LOWER_LEFT))
        text = closest_box.get_text().strip()
        if self.distance(closest_box, x, y, self.LOWER_LEFT) > self._tolerance:
            raise ValidationError(
                'No text elements within %s of (%s,%s) on page %s: '
                'closest is "%s" at (%s,%s)' % (
                    self._tolerance, x, y, page_number, text, closest_box.x0,
                    closest_box.y0))
        return text

    def get_matches(self, page_number, y, x, regex, types, tolerance=None):
        """Get list of values extracted from the PDF element whose corner is
        closest to the given coordinates, optionally within 'tolerance',
        using groups (parentheses) in a regular expression. Values
        are converted from strings to the given types. Raise ValidationError
        if there are 0 matches or the wrong number of matches or any value
        could not be converted to the expected type.

        Commas are removed from strings before converting to 'int' or 'float'.

        Position is allowed to be fuzzy because the regular expression can
        ensure the right cell is picked if it's specific enough. So don't use
        this with a really vague regular expression unless tolerance is low.

        :param page_number: int
        :param y: vertical coordinate
        :param x: horizontal coordinate
        :param regex: regular expression string
        :param types: expected type of each match represented as a callable
        that converts a string to that type, or a list/tuple of them whose
        length corresponds to the number of matches.
        :param tolerance: allowable distance (float) between given coordinates
        and actual coordinates of the matching element.
        :return: resulting value or list of values
        """
        # to tolerate variations in the position of the element, find the
        # closest element within tolerance that matches the regex
        elements = self._find_matching_elements(page_number, y, x, regex)
        closest_element = elements[0]
        if tolerance is not None and self.distance(
                closest_element, x, y, self.LOWER_LEFT) > tolerance:
            raise ValidationError(
                'No text elements within %s of (%s,%s) on page %s: '
                'closest is "%s" at (%s,%s)' % (
                    tolerance, x, y, page_number, closest_element.get_text(),
                    closest_element.x0, closest_element.y0))

        text = closest_element.get_text().strip()
        return self._validate_and_convert_text(regex, text, types)

    def _find_matching_elements(self, page_number, y, x, regex):
        """Return list of text elements matching the given regular expression
        (ignoring surrounding whitespace) in increasing order of distance
        from the given coordinates.

        :param page_number: PDF page number starting with 1.
        :param y: y coordinate (float)
        :param x: x coordinate (float)
        :param regex: regular expression string
        """
        page = self._get_page(page_number)
        matching_elements = [
            e for e in page if isinstance(e, LTTextBox) and
            re.match(regex, e.get_text().strip())]
        if matching_elements == []:
            raise ValidationError(
                'No text elements on page %s match "%s"' % (page_number, regex))
        matching_elements.sort(
            key=lambda e: self.distance(e, x, y, position=self.LOWER_LEFT))
        return matching_elements

    def find_element_coordinates(self, page_number, y, x, regex):
        """Return coordinates of the text element closest to the given
        coordinates matching the given regular expression (ignoring
        surrounding whitespace).

        :param page_number: PDF page number starting with 1.
        :param y: y coordinate (float)
        :param x: x coordinate (float)
        :param regex: regular expression string
        """
        matching_elements = self._find_matching_elements(page_number, y, x,
                                                         regex)
        closest_element = matching_elements[0]
        return (closest_element.y0 - self.offset_y,
                closest_element.x0 - self.offset_x)
