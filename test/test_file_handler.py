from datetime import date
from unittest import TestCase
from hashlib import sha1

from testfixtures import TempDirectory

from billing.processing.state import ReeBill, Address, Customer, UtilBill, Register, Charge, ReeBillCharge
from billing.processing.render import ReebillFileHandler


class ReebillFileHandlerTest(TestCase):
    def setUp(self):
        self.temp_dir = TempDirectory()
        self.file_handler = ReebillFileHandler(self.temp_dir.path)

    def tearDown(self):
        # TODO: this seems to not always remove the directory?
        self.temp_dir.cleanup()

    def test_render(self):
        '''Simple test of reebill PDF rendering that checks whether the PDF
        file matches the expected value. This will tell you when something is
        broken but it won't tell you what's broken.
        '''
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

        r = ReeBill(c, 1, discount_rate=0.3, late_charge_rate=0.1,
                    billing_address=ba, service_address=sa, utilbills=[u])
        r.replace_readings_from_utility_bill_registers(u)
        r.charges = [
            ReeBillCharge(r, 'A', 'Example Charge A', 'Supply', 10, 20, 'kWh',
                          1, 10, 20),
            ReeBillCharge(r, 'B', 'Example Charge B', 'Distribution', 30, 40,
                          'kWh', 1, 30, 40),
        ]

        self.file_handler.render(r)

        # get hash of the PDF file, excluding certain parts where ReportLab puts data
        # that are different every time (current date, and some mysterious bytes)
        path = self.file_handler.get_file_path(r)
        with open(path, 'rb') as pdf_file:
            filtered_lines, prev_line = [], ''
            while True:
                line = pdf_file.readline()
                if line == '':
                    break
                if not (line.startswith(' /CreationDate (D:') or
                        prev_line.startswith(' % ReportLab generated PDF '
                        'document -- digest (http://www.reportlab.com)')):
                    filtered_lines.append(line)
                prev_line = line
        filtered_pdf_hash = sha1(''.join(filtered_lines)).hexdigest()

        # NOTE this will need to be updated whenever the PDF is actually
        # supposed to be different. the only way to do it is to manually verify
        # that the PDF looks right, then get its actual hash and paste it here
        # to make sure it stays that way.
        self.assertEqual('6fed8edcfb0b2927715158b6fcf9a2e4ccb16e8b',
                filtered_pdf_hash)

