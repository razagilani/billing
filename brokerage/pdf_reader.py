"""Code related to getting quotes out of PDF files.
"""
from pdfminer.layout import LTTextBox
from brokerage.reader import Reader
from core.exceptions import ValidationError
from util.pdf import PDFUtil


class PDFReader(Reader):
    """Implementation of Reader for extracting tabular data from PDFs.
    """
    def __init__(self, tolerance=15):
        self._tolerance = tolerance
        self._pages = None

    def load_file(self, quote_file, file_format):
        """Read from 'quote_file'.
        :param quote_file: file to read from.
        :param file_format: ignored.
        """
        self._pages = PDFUtil().get_pdfminer_layout(quote_file)

    def is_loaded(self):
        return self._pages != None

    def get(self, page_number, y, x, the_type):
        """
        Extract a value from the text box in the PDF file whose upper left
        corner is closest to the given coordinates, within some tolerance.

        :param page_specifier: PDF page number starting with 1.
        :param y: vertical coordinate (starting from bottom)
        :param x: horizontal coordinate (starting from left)
        :param the_type: ignored. all values are strings.
        :return: text box content (string), with whitespace stripped
        """
        # get the page
        try:
            page = self._pages[page_number - 1]
        except IndexError:
            raise ValidationError('No page %s: last page number is %s' % (
                page_number, len(self._pages)))

        # get all text boxes (there must be at least one)
        text_boxes = list(
            element for element in page if isinstance(element, LTTextBox))
        if text_boxes == []:
            raise ValidationError('No text elements on page %s' % page_number)

        # find closest box to the given coordinates, within tolerance
        def distance(box):
            return ((box.x0 - x) ** 2 + (box.y0 - y) ** 2)**.5
        closest_box = min(text_boxes, key=distance)
        text = closest_box.get_text().strip()
        if distance(closest_box) > self._tolerance:
            raise ValidationError(
                'No text elements within %s of (%s,%s) on page %s: '
                'closest is "%s" at (%s,%s)' % (
                    self._tolerance, x, y, page_number, text, closest_box.x0,
                    closest_box.y0))
        return text
