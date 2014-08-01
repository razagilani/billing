from billing.test.setup_teardown import init_logging, TestCaseWithSetup
init_logging()




import unittest
from datetime import date, datetime, timedelta
import MySQLdb
import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
import pymongo
from billing import init_config, init_model
from billing.processing import state
from billing.processing.state import Customer, UtilBill, ReeBill, Session, \
    Address
from billing.processing import mongo
from billing.util import dateutils
from billing.processing.session_contextmanager import DBSession
from billing.exc import NoSuchBillException
from billing.test import utils, example_data

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateTest(TestCaseWithSetup):



    def setUp(self):
        # clear out database
        init_config('tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)
        #mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        #self._clear_tables(mysql_connection)

        # insert one customer (not relying on StateDB)
        # c = mysql_connection.cursor()
        # c.execute('''insert into customer
        #         (name, account, discountrate, latechargerate,
        #         utilbill_template_id, bill_email_recipient) values
        #         ('Test Customer', 99999, .12, .34,
        #         '000000000000000000000000', 'example@example.com')''')
        # mysql_connection.commit()

        #session = Session()

        blank_address = Address()
        customer = Customer('Test Customer', 99999, .12, .34,
                            'example@example.com', 'FB Test Utility Name',
                            'FB Test Rate Class', blank_address, blank_address)
        self.session.add(customer)
        self.session.commit()
        #init_config('tstsettings.cfg')
        #init_model()

        self.state_db = state.StateDB()
        # self.reebill_dao = mongo.ReebillDAO(self.state_db,
        #         pymongo.Connection(billdb_config['host'],
        #         int(billdb_config['port']))[billdb_config['database']])

        #self.session = Session()

    def tearDown(self):
        self.session.commit()

        # clear out tables in mysql test database (not relying on StateDB)
        #mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        #self._clear_tables(mysql_connection)

    def test_trim_hypothetical_utilbills(self):
        account, service = '99999', 'gas'
        today = datetime.utcnow().date()
        customer = self.session.query(Customer).filter_by(account=account).one()

        # when there are no utility bills, trim_hypothetical_utilbills
        # should do nothing
        assert self.session.query(UtilBill).count() == 0
        self.state_db.trim_hypothetical_utilbills(account, service)
        self.assertEqual(0, self.session.query(UtilBill).count())

        # TODO add tests for other services to make sure e.g. "electric"
        # bills are unaffected

        # to simplify the utility-bill-creation API
        def create_bill(start, end, state):
            self.session.add(UtilBill(customer, state, 'gas',
                    'washgas', 'DC Non Residential Non Heat', Address(),
                    Address(), period_start=start, period_end=end,
                    date_received=today))

        # when there are only Hypothetical utility bills,
        # trim_hypothetical_utilbills should remove all of them
        create_bill(date(2012,1,1), date(2012,2,1), UtilBill.Hypothetical)
        create_bill(date(2012,2,1), date(2012,3,1), UtilBill.Hypothetical)
        create_bill(date(2012,6,1), date(2012,7,1), UtilBill.Hypothetical)
        self.state_db.trim_hypothetical_utilbills(account, service)
        self.assertEqual(0, self.session.query(UtilBill).count())

        # 2 Complete bills
        create_bill(date(2012,1,1), date(2012,2,1), UtilBill.Complete)
        create_bill(date(2012,6,15), date(2012,7,15), UtilBill.Complete)

        # Hypothetical bills before, between, and after the Complete bills
        # (including some overlaps with Complete bills and each other)
        create_bill(date(2011,9,1), date(2011,10,1), UtilBill.Hypothetical)
        create_bill(date(2011,10,1), date(2011,11,15), UtilBill.Hypothetical)
        create_bill(date(2011,11,15), date(2012,1,15), UtilBill.Hypothetical)
        create_bill(date(2012,1,30), date(2012,3,1), UtilBill.Hypothetical)
        create_bill(date(2012,3,1), date(2012,4,1), UtilBill.Hypothetical)
        create_bill(date(2012,6,1), date(2012,7,1), UtilBill.Hypothetical)
        create_bill(date(2012,7,20), date(2012,8,20), UtilBill.Hypothetical)
        create_bill(date(2012,7,20), date(2012,9,1), UtilBill.Hypothetical)

        self.state_db.trim_hypothetical_utilbills(account, service)

        # the survivors should be the ones with at least one period date in
        # the inner interval (end of earliest non-hypothetical bill to
        # start of latest)
        bills = self.state_db.list_utilbills(account)[0]\
                .filter(UtilBill.state==UtilBill.Hypothetical).all()

        # Ensure that the results are sorted in ascending order by period_start
        # because the constant indices used in the assertions below rely on that order
        bills.sort(key=lambda x: x.period_start)

        self.assertEqual(3, len(bills))
        self.assertEqual((date(2012,1,30), date(2012,3,1)),
                (bills[0].period_start, bills[0].period_end))
        self.assertEqual((date(2012,3,1), date(2012,4,1)),
                (bills[1].period_start, bills[1].period_end))
        self.assertEqual((date(2012,6,1), date(2012,7,1)),
                (bills[2].period_start, bills[2].period_end))


    def test_new_reebill(self):
        b = self.state_db.new_reebill('99999', 1)
        self.assertEqual('99999', b.customer.account)
        self.assertEqual(1, b.sequence)
        self.assertEqual(0, b.version)
        self.assertEqual(0, b.issued)

    def test_versions(self):
        '''Tests max_version(), max_issued_version(), increment_version(), and
        the behavior of is_issued() with multiple versions.'''
        acc, seq = '99999', 1
        # initially max_version is 0, max_issued_version is None, and issued
        # is false
        b = self.state_db.new_reebill(acc, seq)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # adding versions of bills for other accounts should have no effect
        self.session.add(Customer('someone', '11111', 0.5, 0.1,
                'customer1@example.com', 'FB Test Utility',
                'FB Test Rate Class', Address(), Address()))
        self.session.add(Customer('someone', '22222', 0.5, 0.1,
                'customer2@example.com', 'FB Test Utility',
                'FB Test Rate Class', Address(), Address()))
        self.state_db.new_reebill('11111', 1)
        self.state_db.new_reebill('11111', 2)
        self.state_db.new_reebill('22222', 1)
        self.state_db.issue('11111', 1)
        self.state_db.issue('22222', 1)
        self.state_db.increment_version('11111', 1)
        self.state_db.increment_version('22222', 1)
        self.state_db.issue('22222', 1)
        self.state_db.increment_version('22222', 1)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq, version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # incrementing version to 1 should fail when the bill is not issued
        self.assertRaises(Exception, self.state_db.increment_version,
                acc, seq)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # issue & increment version to 1
        self.state_db.issue(acc, seq)
        self.assertEqual(True, self.state_db.is_issued(acc, seq)) # default version for is_issued is highest, i.e. 1
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.state_db.increment_version(acc, seq)
        self.assertEqual(1, self.state_db.max_version(acc, seq))
        self.assertEqual(0, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=1))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # issue version 1 & create version 2
        self.state_db.issue(acc, seq)
        self.assertEqual(1, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=1))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.state_db.increment_version(acc, seq)
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=1))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=2))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.assertEqual(2, self.state_db.max_version(acc, seq))
        self.assertEqual(1, self.state_db.max_issued_version(acc, seq))

        # issue version 2
        self.state_db.issue(acc, seq)
        self.assertEqual(2, self.state_db.max_issued_version(acc, seq))


    def test_get_unissued_corrections(self):
        # reebills 1-4, 1-3 issued
        self.state_db.new_reebill('99999', 1)
        self.state_db.new_reebill('99999', 2)
        self.state_db.new_reebill('99999', 3)
        self.state_db.issue('99999', 1)
        self.state_db.issue('99999', 2)
        self.state_db.issue('99999', 3)

        # no unissued corrections yet
        self.assertEquals([],
                self.state_db.get_unissued_corrections('99999'))

        # make corrections on 1 and 3
        self.state_db.increment_version('99999', 1)
        self.state_db.increment_version('99999', 3)
        self.assertEquals([(1, 1), (3, 1)],
                self.state_db.get_unissued_corrections('99999'))

        # issue 3
        self.state_db.issue('99999', 3)
        self.assertEquals([(1, 1)],
                self.state_db.get_unissued_corrections('99999'))

        # issue 1
        self.state_db.issue('99999', 1)
        self.assertEquals([],
                self.state_db.get_unissued_corrections('99999'))

    def test_payments(self):
        acc = '99999'
        # one payment on jan 15
        self.state_db.create_payment(acc, date(2012,1,15), 'payment 1', 100)
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2011,12,1), date(2012,1,14)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,1,16), date(2012,2,1)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,2,1), date(2012,1,1)))
        payments = self.state_db.find_payment(acc, date(2012,1,1),
                date(2012,2,1))
        p = payments[0]
        self.assertEqual(1, len(payments))
        self.assertEqual((acc, datetime(2012,1,15), 'payment 1', 100),
                (p.customer.account, p.date_applied, p.description,
                p.credit))
        self.assertDatetimesClose(datetime.utcnow(), p.date_received)
        # should be editable since it was created today
        #self.assertEqual(True, p.to_dict()['editable'])

        # another payment on feb 1
        self.state_db.create_payment(acc, date(2012, 2, 1),
                'payment 2', 150)
        self.assertEqual([p], self.state_db.find_payment(acc,
                date(2012,1,1), date(2012,1,31)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,2,2), date(2012,3,1)))
        payments = self.state_db.find_payment(acc, date(2012,1,16),
                date(2012,3,1))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,2,1), 'payment 2', 150),
                (q.customer.account, q.date_applied, q.description,
                q.credit))
        self.assertEqual(sorted([p, q]), sorted(self.state_db.payments(acc)))

        # update feb 1: move it to mar 1
        self.state_db.update_payment(q.id, datetime(2012,3,1),
                    'new description', 200)
        payments = self.state_db.find_payment(acc, datetime(2012,1,16),
                datetime(2012,3,2))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,3,1), 'new description', 200),
                (q.customer.account, q.date_applied, q.description,
                q.credit))

        # delete jan 15
        self.state_db.delete_payment(p.id)
        self.assertEqual([q], self.state_db.find_payment(acc,
                datetime(2012,1,1), datetime(2012,4,1)))


    def test_get_last_reebill(self):
        customer = self.session.query(Customer).one()

        self.assertEqual(None, self.state_db.get_last_reebill('99999'))
        empty_address = Address()
        utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                'DC Non Residential Non Heat', empty_address, empty_address,
                period_start=date(2000,1,1), period_end=date(2000,2,1))
        reebill = ReeBill(customer, 1, 0, utilbills=[utilbill])
        self.session.add(utilbill)
        self.session.add(reebill)

        self.assertEqual(reebill, self.state_db.get_last_reebill('99999'))
        self.assertEqual(None, self.state_db.get_last_reebill(
                '99999', issued_only=True))

    def test_get_last_real_utilbill(self):
        customer = self.session.query(Customer).one()

        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999',
                date(2001,1,1))

        # one bill
        empty_address = Address()
        gas_bill_1 = UtilBill(customer, 0, 'gas', 'washgas',
                'DC Non Residential Non Heat', empty_address, empty_address,
                period_start=date(2000,1,1), period_end=date(2000,2,1))
        self.session.add(gas_bill_1)

        self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                '99999', date(2000,3,1)))
        self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                '99999', date(2000,2,1)))
        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999', date(2000,1,31))

        # two bills
        electric_bill = UtilBill(customer, 0, 'electric', 'pepco',
                'whatever', empty_address, empty_address,
                period_start=date(2000,1,2), period_end=date(2000,2,2))
        self.assertEqual(electric_bill,
                self.state_db.get_last_real_utilbill('99999', date(2000, 3, 1)))
        self.assertEqual(electric_bill,
                self.state_db.get_last_real_utilbill('99999', date(2000, 2, 2)))
        self.assertEqual(gas_bill_1,
                self.state_db.get_last_real_utilbill('99999', date(2000, 2, 1)))
        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999', date(2000,1,31))

        # electric bill is ignored if service "gas" is specified
        self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                '99999', date(2000,2,2), service='gas'))
        self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                '99999', date(2000,2,1), service='gas'))
        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999',
                date(2000,1,31), service='gas')

        # filter by utility and rate class
        self.assertEqual(gas_bill_1,
                self.state_db.get_last_real_utilbill('99999',
                date(2000,3,1), utility='washgas'))
        self.assertEqual(gas_bill_1,
                self.state_db.get_last_real_utilbill('99999',
                date(2000,3,1), rate_class='DC Non Residential Non Heat'))
        self.assertEqual(electric_bill,
                self.state_db.get_last_real_utilbill('99999',
                date(2000,3,1), utility='pepco', rate_class='whatever'))
        self.assertEqual(electric_bill,
                self.state_db.get_last_real_utilbill('99999',
                date(2000,3,1), rate_class='whatever'))
        self.assertEqual(electric_bill,
                self.state_db.get_last_real_utilbill('99999',
                date(2000,3,1), utility='pepco', rate_class='whatever'))
        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999',
                date(2000,1,31), utility='washgas', rate_class='whatever')

        # hypothetical utility bills are always ignored
        gas_bill_1.state = UtilBill.Hypothetical
        electric_bill.state = UtilBill.Hypothetical
        self.assertRaises(NoSuchBillException,
                self.state_db.get_last_real_utilbill, '99999', date(2000,3,1))


if __name__ == '__main__':
    unittest.main()
