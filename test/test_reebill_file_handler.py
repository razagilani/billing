from datetime import date
from errno import ENOENT
from unittest import TestCase
from hashlib import sha1
import os.path

from testfixtures import TempDirectory

from billing.core.model import Address, Customer, UtilBill, \
    Register
from billing.reebill.state import ReeBill, ReeBillCharge
from billing.reebill.render import ReebillFileHandler


class ReebillFileHandlerTest(TestCase):
    def setUp(self):
        self.temp_dir = TempDirectory()
        self.file_handler = ReebillFileHandler(self.temp_dir.path)

        ba = Address(addressee='Billing Addressee', street='123 Example St.',
                     city='Washington', state='DC', postal_code='01234')
        sa = Address(addressee='Service Addressee', street='456 Test Ave.',
                     city='Washington', state='DC', postal_code='12345')
        c = Customer('Test Customer', '00001', 0.2, 0.1, 'test@example.com',
                     'Test Utility', 'Test Rate Class', ba, sa)
        ba2 = Address.from_other(ba)
        ba2.addressee = 'Reebill Billing Addressee'
        sa2 = Address.from_other(sa)
        ba2.addressee = 'Reebill Service Addressee'
        ba3 = Address.from_other(ba)
        ba2.addressee = 'Utility Billing Addressee'
        sa3 = Address.from_other(sa)
        ba2.addressee = 'Utility Service Addressee'
        u = UtilBill(c, UtilBill.Complete, 'electric', 'Test Utility', 'Test Rate Class', ba3, sa3,
                     period_start=date(2000,1,1), period_end=date(2000,2,1))
        u.registers = [Register(u, 'All energy', 100, 'therms', 'REGID',
                                False, 'total', 'REG_TOTAL', [], 'METERID')]
        self.reebill = ReeBill(c, 1, discount_rate=0.3, late_charge_rate=0.1,
                    billing_address=ba, service_address=sa, utilbills=[u])
        self.reebill.replace_readings_from_utility_bill_registers(u)
        self.reebill.charges = [
            ReeBillCharge(self.reebill, 'A', 'Example Charge A', 'Supply', 10, 20, 'kWh',
                          1, 10, 20),
            ReeBillCharge(self.reebill, 'B', 'Example Charge B', 'Distribution', 30, 40,
                          'kWh', 1, 30, 40),
            ]

        self.file_handler.render(self.reebill)
        # TODO: this seems to not always remove the directory?
        self.temp_dir.cleanup()

    def test_render_delete(self):
        '''Simple test of creating and deleting a reebill PDF file. Checking
        whether the PDF file matches the expected value will tell you when
        something is broken but it won't tell you what's broken.
        '''
        self.file_handler.render(self.reebill)

        # get hash of the PDF file, excluding certain parts where ReportLab puts data
        # that are different every time (current date, and some mysterious bytes)
        path = self.file_handler.get_file_path(self.reebill)
        line_filters = [
            lambda prev_line, cur_line: cur_line.startswith(
                    ' /CreationDate (D:'),
            lambda prev_line, cur_line: prev_line.startswith(
                    ' % ReportLab generated PDF document -- digest '
                    '(http://www.reportlab.com)'),
            lambda prev_line, cur_line: cur_line.startswith("%% 'fontFile'"),
            lambda prev_line, cur_line: cur_line.startswith('! 0000'),
            lambda prev_line, cur_line: prev_line.startswith('  startxref'),
        ]
        with open(path, 'rb') as pdf_file:
            filtered_lines, prev_line = [], ''
            while True:
                line = pdf_file.readline()
                print line
                if line == '':
                    break
                if not any(f(prev_line, line) for f in line_filters):
                    filtered_lines.append(line)
                prev_line = line
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('c6eb0cf1f0fa0d3df4a57c9f49bb862574546ef2',
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
