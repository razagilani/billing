from datetime import date, datetime

from sqlalchemy.orm.exc import NoResultFound

from reebill.reebill_model import ReeBillCustomer, ReeBill
from core import init_config, init_model
from core.model import Session, Address, Utility, Supplier, RateClass, \
    UtilityAccount
from reebill.reebill_model import ReeBill, ReeBillCustomer
from reebill.payment_dao import PaymentDAO
from reebill.reebill_dao import ReeBillDAO
from test.setup_teardown import clear_db
from test.testing_utils import TestCase


class StateDBTest(TestCase):

    def setUp(self):
        # clear out database
        init_config('test/tstsettings.cfg')
        init_model()
        clear_db()
        blank_address = Address()
        test_utility = Utility(name='FB Test Utility Name',
                               address=blank_address)
        test_supplier = Supplier(name='FB Test Suplier', address=blank_address)
        self.utility_account = UtilityAccount('someaccount', 99999,
                            test_utility, test_supplier,
                            RateClass(name='FB Test Rate Class',
                                      utility=test_utility, service='gas'),
                            blank_address, blank_address)
        self.reebill_customer = ReeBillCustomer(name='Test Customer',
                                    discount_rate=.12, late_charge_rate=.34,
                                    service='thermal',
                                    bill_email_recipient='example@example.com',
                                    utility_account=self.utility_account)
        self.reebill_customer2 = self.reebill_customer.clone()

        self.session = Session()
        self.session.add(self.utility_account)
        self.session.add(self.reebill_customer)
        self.session.commit()
        self.state_db = ReeBillDAO()
        self.payment_dao = PaymentDAO()

    def tearDown(self):
        clear_db()

    def test_get_all_reebills_for_account(self):
        session = Session()

        reebills = [
            ReeBill(self.reebill_customer, 1),
            ReeBill(self.reebill_customer, 2),
            ReeBill(self.reebill_customer, 3)
        ]

        for rb in reebills:
            session.add(rb)

        account = self.reebill_customer.get_account()
        bills = self.state_db.get_all_reebills_for_account(account)
        self.assertEqual(bills, reebills)

    def test_payments(self):
        acc = '99999'
        # one payment on jan 15
        self.payment_dao.create_payment(acc, date(2012,1,15), 'payment 1', 100)
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2011,12,1), date(2012,1,14)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,1,16), date(2012,2,1)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,2,1), date(2012,1,1)))
        payments = self.payment_dao.find_payment(acc, date(2012,1,1),
                date(2012,2,1))
        p = payments[0]
        self.assertEqual(1, len(payments))
        self.assertEqual((acc, datetime(2012,1,15), 'payment 1', 100),
                (p.reebill_customer.get_account(), p.date_applied, p.description,
                p.credit))
        self.assertDatetimesClose(datetime.utcnow(), p.date_received)
        # should be editable since it was created today
        #self.assertEqual(True, p.to_dict()['editable'])

        # another payment on feb 1
        self.payment_dao.create_payment(acc, date(2012, 2, 1),
                'payment 2', 150)
        self.assertEqual([p], self.payment_dao.find_payment(acc,
                date(2012,1,1), date(2012,1,31)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,2,2), date(2012,3,1)))
        payments = self.payment_dao.find_payment(acc, date(2012,1,16),
                date(2012,3,1))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,2,1), 'payment 2', 150),
                (q.reebill_customer.get_account(), q.date_applied, q.description,
                q.credit))
        self.assertEqual(sorted([p, q]),
                         sorted(self.payment_dao.get_payments(acc)))

        # update feb 1: move it to mar 1
        q.date_applied = datetime(2012,3,1)
        q.description = 'new description'
        q.credit = 200
        payments = self.payment_dao.find_payment(acc, datetime(2012,1,16),
                datetime(2012,3,2))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,3,1), 'new description', 200),
                (q.reebill_customer.get_account(), q.date_applied, q.description,
                q.credit))

        # delete jan 15
        self.payment_dao.delete_payment(p.id)
        self.assertEqual([q], self.payment_dao.find_payment(acc,
                datetime(2012,1,1), datetime(2012,4,1)))

    def test_get_issuable_reebills(self):
        session = Session()

        rb1 = ReeBill(self.reebill_customer, 1)
        rb1.issued = True
        rb1.processed = True
        rb1_1 = ReeBill(self.reebill_customer, 1, version=1)
        rb1_1.processed = True
        rb2 = ReeBill(self.reebill_customer, 2)
        rb2.processed = True
        rb3 = ReeBill(self.reebill_customer2, 1)
        rb3.processed = True

        session.add_all([rb1, rb1_1, rb2, rb3])

        self.assertEqual(
            self.state_db.get_issuable_reebills().all(),
            [rb2, rb3]
        )