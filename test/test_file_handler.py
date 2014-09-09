from datetime import date
from unittest import TestCase
from hashlib import sha1

from testfixtures import TempDirectory

from billing.processing.state import ReeBill, Address, Customer, UtilBill, Register, Charge, ReeBillCharge
from billing.processing.render import ReebillFileHandler


class ReebillFileHandlerTest(TestCase):
    def setUp(self):
        self.temp_dir = TempDirectory()
        self.renderer = ReebillFileHandler(self.temp_dir.path)

    def tearDown(self):
        # TODO: this seems to not always remove the directory?
        self.temp_dir.cleanup()

    def test_render(self):
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
        u.registers = [Register(u, '', 100, 'therms', '', False, 'total', 'REG_TOTAL', [], '')]

        r = ReeBill(c, 1, discount_rate=0.3, late_charge_rate=0.1,
                    billing_address=ba, service_address=sa, utilbills=[u])
        r.replace_readings_from_utility_bill_registers(u)
        r.charges = [
            ReeBillCharge(r, 'A', 'Example Charge A', 'Supply', 10, 20, 'kWh',
                          1, 1, 10, 20),
            ReeBillCharge(r, 'B', 'Example Charge B', 'Distribution', 30, 40, 'kWh',
                          1, 1, 30, 40),
        ]

        # TODO: put some actual data in this bill

        self.renderer.render(r)

        with open(self.renderer.get_file_path(r), 'rb') as pdf_file:
            pdf_hash = sha1(pdf_file.read()).hexdigest()

        # TODO: PDF file comes out different every time?
        #self.assertEqual('3a4df0883354b404397c527b815409dada09f493', pdf_hash)
