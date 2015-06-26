from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError
from pyPdf import PdfFileWriter, PdfFileReader

# TODO: no test coverage
class PDFUtil(object):
    """Misc methods for working with PDF file contents.
    """
    def get_pdf_text(pdf_file):
        """Get all text from a PDF file.
        :param pdf_file: file object
        """
        pdf_file.seek(0)
        rsrcmgr = PDFResourceManager()
        outfile = StringIO()
        laparams = LAParams()  # Use this to tell interpreter to capture newlines
        # laparams = None
        device = TextConverter(rsrcmgr, outfile, codec='utf-8',
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
