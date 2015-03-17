from pyPdf import PdfFileWriter, PdfFileReader

class PDFConcatenator(object):
    """Accumulates PDF files into one big PDF file.
    """
    def __init__(self):
        self._writer = PdfFileWriter()

    def append(self, pdf_file):
        reader = PdfFileReader(pdf_file)
        for page_num in xrange(reader.numPages):
            self._writer.addPage(reader.getPage(page_num))

    def write_result(self, output_file):
        self._writer.write(output_file)
