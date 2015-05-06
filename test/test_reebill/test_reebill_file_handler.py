from StringIO import StringIO
from mock import Mock, call
from test import init_test_config
from util.pdf import PDFConcatenator

init_test_config()

from datetime import date
from errno import ENOENT
from unittest import TestCase
from hashlib import sha1
import os.path

from testfixtures import TempDirectory

from core.model import Address, UtilBill, \
    Register, UtilityAccount
from reebill.reebill_model import ReeBill, ReeBillCharge, ReeBillCustomer
from reebill.reebill_file_handler import ReebillFileHandler, \
    SummaryFileGenerator


class ReebillFileHandlerTest(TestCase):
    def setUp(self):
        from core import config
        self.temp_dir = TempDirectory()
        self.file_handler = ReebillFileHandler(
                self.temp_dir.path,
                config.get('reebill', 'teva_accounts'))

        ba = Address(addressee='Billing Addressee', street='123 Example St.',
                     city='Washington', state='DC', postal_code='01234')
        sa = Address(addressee='Service Addressee', street='456 Test Ave.',
                     city='Washington', state='DC', postal_code='12345')
        utility_account = UtilityAccount('someaccount', '00001',
                        'Test Utility', 'Test Supplier', 'Test Rate Class',
                        ba, sa)
        c = ReeBillCustomer(name='Test Customer', discount_rate=0.2,
                            late_charge_rate=0.1,
                            bill_email_recipient='test@example.com',
                            service='thermal', utility_account=utility_account)
        ba2 = ba.clone()
        ba2.addressee = 'Reebill Billing Addressee'
        sa2 = sa.clone()
        ba2.addressee = 'Reebill Service Addressee'
        ba3 = ba.clone()
        ba2.addressee = 'Utility Billing Addressee'
        sa3 = sa.clone()
        ba2.addressee = 'Utility Service Addressee'
        u = UtilBill(utility_account, None, None,
                     supplier='Test Supplier', billing_address=ba3,
                     service_address=sa3, period_start=date(2000, 1, 1),
                     period_end=date(2000, 2, 1))
        u.registers = [Register(Register.TOTAL, 'therms', quantity=100,
                                identifier='REGID', meter_identifier='METERID',
                                reg_type='total', description='All energy')]
        self.reebill = ReeBill(c, 1, discount_rate=0.3, late_charge_rate=0.1,
                    billing_address=ba, service_address=sa, utilbills=[u])
        self.reebill.replace_readings_from_utility_bill_registers(u)
        self.reebill.charges = [
            ReeBillCharge(self.reebill, 'A', 'Example Charge A', 'Supply',
                          10, 20, 'therms', 1, 10, 20),
            ReeBillCharge(self.reebill, 'B', 'Example Charge B', 'Distribution',
                          30, 40, 'therms', 1, 30, 40),
            # charges are not in group order to make sure they are sorted
            # before grouping; otherwise some charges could be omitted
            # (this was bug #80340044)
            ReeBillCharge(self.reebill, 'C', 'Example Charge C', 'Supply', 50,
                          60, 'therms', 1, 50, 60),
        ]

        self.file_handler.render(self.reebill)

    def tearDown(self):
        # TODO: this seems to not always remove the directory?
        self.temp_dir.cleanup()

    def test_file_name_path(self):
        expected_name = '%s_%04d.pdf' % (
            self.reebill.get_account(), self.reebill.sequence)
        self.assertEqual(expected_name,
                         self.file_handler.get_file_name(self.reebill))
        file_path = self.file_handler.get_file_path(self.reebill)
        self.assertTrue(file_path.endswith(expected_name))
        self.assertTrue(file_path.startswith(self.temp_dir.path))

    def _filter_pdf_file(self, pdf_file):
        '''Read 'pdf_file' and return a list of lines from the file excluding
        parts where ReportLab puts data that are different every time (current
        date, font file paths, and some mysterious bytes).
        '''
        line_filters = [
            lambda prev_line, cur_line: cur_line.startswith(
                ' /CreationDate (D:'),
            lambda prev_line, cur_line: prev_line.startswith(
                ' % ReportLab generated PDF document -- digest '
                '(http://www.reportlab.com)'),
            lambda prev_line, cur_line: cur_line.startswith("% 'fontFile"),
            lambda prev_line, cur_line: cur_line.startswith('0000'),
            lambda prev_line, cur_line: prev_line.startswith('startxref'),
        ]
        filtered_lines, prev_line = [], ''
        while True:
            line = pdf_file.readline()
            if line == '':
                break
            if not any(f(prev_line, line) for f in line_filters):
                filtered_lines.append(line)
            prev_line = line
        return filtered_lines

    def test_render_delete(self):
        '''Simple test of creating and deleting a reebill PDF file. Checking
        whether the PDF file matches the expected value will tell you when
        something is broken but it won't tell you what's broken.
        '''
        # directory for the PDF already exists by before 'render' is called
        self.file_handler.render(self.reebill)

        # get hash of the PDF file, excluding certain parts where ReportLab
        # puts data that are different every time
        path = self.file_handler.get_file_path(self.reebill)
        with open(path, 'rb') as pdf_file:
            filtered_lines = self._filter_pdf_file(pdf_file)
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('b77a53a66eed69b1025a64a094112db7be91283e',
                filtered_pdf_hash)

        # delete the file
        self.assertTrue(os.path.isfile(path))
        self.file_handler.delete_file(self.reebill)
        self.assertFalse(os.path.exists(path))

        # since the file is now gone, deleting it will raise an OSError
        with self.assertRaises(OSError) as context:
            self.file_handler.delete_file(self.reebill)
        self.assertEqual(ENOENT, context.exception.errno)

        # unless ignore_missing == True
        self.file_handler.delete_file(self.reebill, ignore_missing=True)

    def test_render_teva(self):
        '''Render a bill using the "skin" (directory containing image files)
        called "teva". This also checks the creation of the directory to
        contain the PDF because it doesn't exist when 'render' is called.
        '''
        # tstsettings.cfg specifies that if the customer's account number is
        # this one, it willl get the "teva" images on its bill PDFs.
        self.reebill.reebill_customer.utility_account.account = 'teva'
        self.file_handler.render(self.reebill)

        # get hash of the PDF file, excluding certain parts where ReportLab puts data
        # that are different every time
        path = self.file_handler.get_file_path(self.reebill)
        self.assertEqual(os.path.isabs(path), True)

        with open(path, 'rb') as pdf_file:
            filtered_lines = self._filter_pdf_file(pdf_file)
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('2daa743d667ecd2b4cd4724340ce3bbf560eec56',
                         filtered_pdf_hash)


class SummaryFileGeneratorTest(TestCase):
    """Unit test for SummaryFileGenerator.
    """
    def setUp(self):
        self.reebill_1 =Mock(autospec=ReeBill)
        self.reebill_2 = Mock(autospec=ReeBill)
        self.file1, self.file2 = StringIO('1'), StringIO('2')
        self.reebills = [Mock]
        self.reebill_file_handler = Mock(autospec=ReebillFileHandler)
        self.reebill_file_handler.get_file.side_effect = [self.file1,
                                                          self.file2]
        self.pdf_concatenator = Mock(autospec=PDFConcatenator)
        self.output_file = StringIO()
        self.sfg = SummaryFileGenerator(self.reebill_file_handler,
                                        self.pdf_concatenator)

    def test_generate_summary_file(self):
        self.sfg.generate_summary_file([self.reebill_1, self.reebill_2],
                                       self.output_file)
        self.reebill_file_handler.render.assert_has_calls(
            [call(self.reebill_1), call(self.reebill_2)])
        self.reebill_file_handler.get_file.assert_has_calls(
            [call(self.reebill_1), call(self.reebill_2)])
        self.pdf_concatenator.append.assert_has_calls(
            [call(self.file1), call(self.file2)])
        self.pdf_concatenator.write_result.assert_called_once_with(
            self.output_file)

