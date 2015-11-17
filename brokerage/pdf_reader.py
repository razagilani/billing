from brokerage.reader import Reader


class PDFReader(Reader):
    """Implementation of Reader for extracting tabular data from PDFs.
    """
    TOLERANCE = 10

    def load_file(self, quote_file, file_format):
        # TODO
        raise NotImplementedError

    def is_loaded(self):
        # TODO
        raise NotImplementedError

    def get(self, page_number, y, x, the_type):
        """
        Extract a value from the text box in the PDF file whose upper left
        corner is closest to the given coordinates, within some tolerance.

        :param page_specifier: PDF page number starting with 1.
        :param y: vertical coordinate
        :param x: horizontal coordinate
        :param the_type: expected type of the value
        """
        # TODO
        raise NotImplementedError
