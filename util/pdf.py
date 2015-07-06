from io import BytesIO
import re
from pdfminer.converter import TextConverter, PDFPageAggregator
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError, PDFParser
from pyPdf import PdfFileWriter, PdfFileReader
import sys


def fix_pdfminer_cid(text):
    def sub_cid(match):
        val = int(match.group(1))
        return chr(val) if val < 128 else "!"
    text = re.sub(r"\(cid:(\d+?)\)",
        sub_cid, text)
    return text

class PDFPageAggregatorFixedCID(PDFPageAggregator):
    """
    Overrides the default 'PDFPageAggregator' class to better handle issues
    with unicode fonts. Instead of returning (cid:###) when encountering an
    unknown charater, the character is converted to ASCII and then returned,
    if possible. Otherwise, a '!' is returned.
    """
    def handle_undefined_char(self, font, cid):
        if self.debug:
            print >>sys.stderr, 'undefined: %r, %r' % (font, cid)
        return chr(cid) if cid < 128 else "!"

class TextConverterFixedCID(TextConverter):
    """
    Overrides the default 'TextConverter' class to better handle issues
    with unicode fonts. Instead of returning (cid:###) when encountering an
    unknown charater, the character is converted to ASCII and then returned,
    if possible. Otherwise, a '!' is returned.
    """
    def handle_undefined_char(self, font, cid):
        if self.debug:
            print >>sys.stderr, 'undefined: %r, %r' % (font, cid)
        return chr(cid) if cid < 128 else "!"

# TODO: no test coverage
class PDFUtil(object):
    """Misc methods for working with PDF file contents.
    """
    def get_pdf_text(self, pdf_file):
        """Get all text from a PDF file.
        :param pdf_file: file object
        """
        pdf_file.seek(0)
        rsrcmgr = PDFResourceManager()
        outfile = BytesIO()
        laparams = LAParams()  # Use this to tell interpreter to capture newlines
        # laparams = None
        device = TextConverterFixedCID(rsrcmgr, outfile, codec='utf-8',
                               laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        try:
            for page in PDFPage.get_pages(pdf_file, set(),
                                          check_extractable=True):
                interpreter.process_page(page)
        except PDFSyntaxError:
            text = ''
        else:
            outfile.seek(0)
            text = outfile.read()
            text = unicode(text, errors='ignore')
        device.close()
        return text

    def get_pdf_layout(self, pdf_file):
        pdf_file.seek(0)
        parser = PDFParser(pdf_file)
        document = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        laparams = LAParams()
        device = PDFPageAggregatorFixedCID(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        try:
            pages = []
            for page in PDFPage.create_pages(document):
                interpreter.process_page(page)
                pages.append(device.get_result())
        except PDFSyntaxError as e:
            pages = []
            print e
        device.close()

        return pages


class PDFConcatenator(object):
    """Accumulates PDF files into one big PDF file.
    """
    def __init__(self):
        self._writer = PdfFileWriter()
        self._input_files = []

    def __del__(self):
        self.close_input_files()

    def append(self, pdf_file):
        reader = PdfFileReader(pdf_file)
        for page_num in xrange(reader.numPages):
            self._writer.addPage(reader.getPage(page_num))
            self._input_files.append(pdf_file)

    def write_result(self, output_file):
        self._writer.write(output_file)

    def close_input_files(self):
        """Close any input files that are still open. PyPdf reads from input
        files while reading the output so this should not be called until
        after 'write_output'.
        """
        for f in self._input_files:
            f.close()
