from billing.test import init_test_config
init_test_config()

from datetime import date
from errno import ENOENT
from unittest import TestCase
from hashlib import sha1
import os.path

from testfixtures import TempDirectory

from billing.core.model import Address, Customer, UtilBill, \
    Register, UtilityAccount, ReeBillCustomer
from billing.reebill.state import ReeBill, ReeBillCharge
from billing.reebill.reebill_file_handler import ReebillFileHandler
from billing import init_config

init_config(filepath='test/tstsettings.cfg')

class ReebillFileHandlerTest(TestCase):
    def setUp(self):
        from billing import config
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
        c = ReeBillCustomer('Test Customer', 0.2, 0.1, 'test@example.com',
                            'thermal', utility_account)
        ba2 = Address.from_other(ba)
        ba2.addressee = 'Reebill Billing Addressee'
        sa2 = Address.from_other(sa)
        ba2.addressee = 'Reebill Service Addressee'
        ba3 = Address.from_other(ba)
        ba2.addressee = 'Utility Billing Addressee'
        sa3 = Address.from_other(sa)
        ba2.addressee = 'Utility Service Addressee'
        u = UtilBill(utility_account, UtilBill.Complete, 'electric', 'Test Utility', 'Test Supplier',
            'Test Rate Class', ba3, sa3, period_start=date(2000,1,1),
            period_end=date(2000,2,1))
        u.registers = [Register(u, 'All energy', 'REGID', 'therms', False,
                                'total', [], 'METERID', quantity=100,
                                register_binding='REG_TOTAL')]
        self.reebill = ReeBill(c, 1, discount_rate=0.3, late_charge_rate=0.1,
                    billing_address=ba, service_address=sa, utilbills=[u])
        self.reebill.replace_readings_from_utility_bill_registers(u)
        self.reebill.charges = [
            ReeBillCharge(self.reebill, 'A', 'Example Charge A', 'Supply',
                          10, 20, 'therms', 1, 10, 20),
            ReeBillCharge(self.reebill, 'B', 'Example Charge B', 'Distribution', 30, 40,
                          'therms', 1, 30, 40),
            # charges are not in group order to make sure they are sorted
            # before grouping; otherwise some charges could be omitted
            # (this was bug #80340044)
            ReeBillCharge(self.reebill, 'C', 'Example Charge C', 'Supply', 50, 60,
                          'therms', 1, 50, 60),
        ]

        self.file_handler.render(self.reebill)
        # TODO: this seems to not always remove the directory?
        self.temp_dir.cleanup()

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
        # check the case where the directory for the PDF already exists by
        # creating it before calling 'render'
        path = self.file_handler.get_file_path(self.reebill)
        os.makedirs(os.path.dirname(path))

        self.file_handler.render(self.reebill)

        # get hash of the PDF file, excluding certain parts where ReportLab puts data
        # that are different every time
        with open(path, 'rb') as pdf_file:
            filtered_lines = self._filter_pdf_file(pdf_file)
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('f3e0e94dabfd339933cd4c7913e30c0f73226c1c',
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
        with open(path, 'rb') as pdf_file:
            filtered_lines = self._filter_pdf_file(pdf_file)
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('f479f2a1661fd48dc1107a27e254003b481065bd',
                         filtered_pdf_hash)

