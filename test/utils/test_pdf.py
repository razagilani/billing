import os
from unittest import TestCase
from StringIO import StringIO
from hashlib import sha1
from core import ROOT_PATH
from util.pdf import PDFConcatenator


class TestPDFConcatenator(TestCase):

    def setUp(self):
        # TODO: ideally, this file should not be inside "test_core"
        PATH = os.path.join(ROOT_PATH, 'test/test_core/data/utility_bill.pdf')
        with open(PATH, 'rb') as input_file:
            self.input_pdf = input_file.read()
        self.pdf_concatenator = PDFConcatenator()

    # note: for now, behavior with no files is undefined

    def test_double_file(self):
        """Concatenate the example file with itself.
        """
        out = StringIO()
        in_files = [StringIO(self.input_pdf), StringIO(self.input_pdf)]
        self.pdf_concatenator.append(in_files[0])
        self.pdf_concatenator.append(in_files[1])
        self.pdf_concatenator.write_result(out)
        out.seek(0)
        hash = sha1(out.read()).hexdigest()
        self.assertEqual('dd57b30d125497feb4db1595ea644248f4986911', hash)

        # files get closed when PDFConcatenator is deleted
        self.assertFalse(any(f.closed for f in in_files))
        del self.pdf_concatenator
        self.assertTrue(all(f.closed for f in in_files))

