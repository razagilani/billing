"""Code related to getting quotes out of PDF files.
"""
import re
from pdfminer.layout import LTTextBox
from brokerage.reader import Reader
from core.exceptions import ValidationError
from util.pdf import PDFUtil

def distance(element, x, y):
    """Return distance of a PDF element from the given coordinates.
    """
    return ((element.x0 - x) ** 2 + (element.y0 - y) ** 2)**.5

class PDFReader(Reader):
    """Implementation of Reader for extracting tabular data from PDFs.
    """
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
        closest_box = min(text_boxes, key=lambda box: distance(box, x, y))
        text = closest_box.get_text().strip()
        if distance(closest_box, x, y) > self._tolerance:
            raise ValidationError(
                'No text elements within %s of (%s,%s) on page %s: '
                'closest is "%s" at (%s,%s)' % (
                    self._tolerance, x, y, page_number, text, closest_box.x0,
                    closest_box.y0))
        return text

    def find_element(self, page_number, y, x, regex):
        """Return coordinates of the text element closest to the given
        coordinates matching the given regular expression (ignoring
        surrounding whitespace).

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
            raise ValidationError('No text elements on page %s match "%s"' %
                                  page_number, regex)
        matching_elements.sort(key=lambda e: distance(e, x, y))
        closest_element = matching_elements[0]
        return (closest_element.y0 - self.offset_y,
                closest_element.x0 - self.offset_x)
