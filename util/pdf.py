from pyPdf import PdfFileWriter, PdfFileReader

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
