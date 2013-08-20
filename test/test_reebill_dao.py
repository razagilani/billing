import unittest
import pymongo
import sqlalchemy
import copy
from datetime import date, datetime, timedelta
from bson import ObjectId
import MySQLdb
from billing.util import dateutils
from billing.processing import mongo
from billing.processing.state import StateDB
from billing.processing.state import ReeBill, Customer, UtilBill
from billing.test import example_data, utils
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.mongo import NoSuchBillException, IssuedBillError, NotUniqueException, float_to_decimal
from billing.processing.session_contextmanager import DBSession
from billing.util.dictutils import deep_map
from billing.util.dateutils import date_to_datetime

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillDAOTest(TestCaseWithSetup, utils.TestCase):
    '''Tests for ReeBillDAO, which loads/saves utility bill and reebill
    documents in mongo.
    
    Since this is a TestCaseWithSetup, there is a customer account in MySQL and
    a utility bill template in Mongo before each test, but maybe that should be
    removed since these are more low-level test than TestProcess.'''

    def test_load_reebill(self):
        with DBSession(self.state_db) as session:
            # put some reebills in Mongo, including non-0 versions. note that a
            # sequence-0 utility bill template is already present.
            b0 = example_data.get_reebill('99999', 0, start=date(2012,1,1),
                    end=date(2012,2,1), version=0)
            b1 = example_data.get_reebill('99999', 1, start=date(2012,2,1),
                    end=date(2012,3,1), version=0)
            b1_1 = example_data.get_reebill('99999', 1, start=date(2012,2,1),
                    end=date(2012,3,1), version=1)
            b1_2 = example_data.get_reebill('99999', 1, start=date(2012,2,1),
                    end=date(2012,3,1), version=2)
            b2 = example_data.get_reebill('99999', 2, start=date(2012,3,1),
                    end=date(2012,4,1), version=0)
            b3 = example_data.get_reebill('99999', 3, start=date(2012,4,1),
                    end=date(2012,5,1), version=0)
            b3_1 = example_data.get_reebill('99999', 3, start=date(2012,4,1),
                    end=date(2012,5,1), version=1)

            # change something in each utility bill to make it identifiable:
            # meter identifier works as well as anything else
            b0._utilbills[0]['meters'][0]['identifier'] = 'zero0'
            b1._utilbills[0]['meters'][0]['identifier'] = 'one0'
            b1_1._utilbills[0]['meters'][0]['identifier'] = 'one1'
            b1_2._utilbills[0]['meters'][0]['identifier'] = 'one2'
            b2._utilbills[0]['meters'][0]['identifier'] = 'two0'
            b3._utilbills[0]['meters'][0]['identifier'] = 'three0'
            b3_1._utilbills[0]['meters'][0]['identifier'] = 'three1'
            assert [b._utilbills[0]['meters'][0]['identifier'] for b in [b0,
                    b1, b1_1, b1_2, b2, b3, b3_1]] == ['zero0', 'one0', 'one1',
                    'one2', 'two0', 'three0', 'three1']

            b1.issue_date = date(2012,1,1)
            b1_1.issue_date = date(2012,2,15)
            b1_2.issue_date = date(2012,3,15)
            b2.issue_date = date(2012,2,1)
            b3.issue_date = date(2012,3,1)
            b3_1.issue_date = date(2012,4,15)

            # save reebill docs in Mongo, and add rows in MySQL with each
            # version of each bill. issued reebills need their own frozen
            # utilbills in Mongo, which are created by saving with
            # freeze_utilbills=True.
            self.reebill_dao.save_reebill(b0)
            self.reebill_dao.save_reebill(b1, freeze_utilbills=True)
            self.reebill_dao.save_reebill(b1_1, freeze_utilbills=True)
            self.reebill_dao.save_reebill(b1_2)
            self.reebill_dao.save_reebill(b2)
            self.reebill_dao.save_reebill(b3, freeze_utilbills=True)
            self.reebill_dao.save_reebill(b3_1)
            self.state_db.new_reebill(session, '99999', 1, version=0)
            self.state_db.new_reebill(session, '99999', 1, version=1)
            self.state_db.new_reebill(session, '99999', 1, version=2)
            self.state_db.new_reebill(session, '99999', 2, version=0)
            self.state_db.new_reebill(session, '99999', 3, version=0)
            self.state_db.new_reebill(session, '99999', 3, version=1)

            # freezing of utililty bills should have created one one frozen
            # copy for each issued reebill (3) in addition to the editable one
            # for each sequence (4), plus the template that was already there,
            # for a total of 8
            all_utilbill_docs = self.reebill_dao.load_utilbills(account='99999')
            self.assertEquals(8, len(all_utilbill_docs))

            # with no extra args to load_reebill(), it should load the maximum
            # version
            b0_max = self.reebill_dao.load_reebill('99999', 0)
            b1_max = self.reebill_dao.load_reebill('99999', 1)
            b2_max = self.reebill_dao.load_reebill('99999', 2)
            b3_max = self.reebill_dao.load_reebill('99999', 3)
            self.assertEqual(0, b0_max.sequence)
            self.assertEqual(0, b0_max.version)
            self.assertEqual(1, b1_max.sequence)
            self.assertEqual(2, b1_max.version)
            self.assertEqual(2, b2_max.sequence)
            self.assertEqual(0, b2_max.version)
            self.assertEqual(3, b3_max.sequence)
            self.assertEqual(1, b3_max.version)

            # make sure the right utility bills were found, using meter
            # identifiers set above
            self.assertEqual('zero0',
                    b0_max._utilbills[0]['meters'][0]['identifier'])
            self.assertEqual('one2',
                    b1_max._utilbills[0]['meters'][0]['identifier'])
            self.assertEqual('two0',
                    b2_max._utilbills[0]['meters'][0]['identifier'])
            self.assertEqual('three1',
                    b3_max._utilbills[0]['meters'][0]['identifier'])

            # try getting specific versions
            b1_1 = self.reebill_dao.load_reebill('99999', 1, version=1)
            b1_2 = self.reebill_dao.load_reebill('99999', 1, version=2)
            b3_1 = self.reebill_dao.load_reebill('99999', 3, version=1)
            self.assertEqual(1, b1_1.sequence)
            self.assertEqual(1, b1_1.version)
            self.assertEqual(1, b1_2.sequence)
            self.assertEqual(2, b1_2.version)
            self.assertEqual(1, b3_1.version)
            self.assertEqual('one1',
                    b1_1._utilbills[0]['meters'][0]['identifier'])
            self.assertEqual('one2',
                    b1_2._utilbills[0]['meters'][0]['identifier'])
            self.assertEqual('three1',
                    b3_1._utilbills[0]['meters'][0]['identifier'])
            b0_max = self.reebill_dao.load_reebill('99999', 0, version='max')
            b1_max = self.reebill_dao.load_reebill('99999', 1, version='max')
            b2_max = self.reebill_dao.load_reebill('99999', 2, version='max')
            b3_max = self.reebill_dao.load_reebill('99999', 3, version='max')
            self.assertEqual(0, b0_max.version)
            self.assertEqual(2, b1_max.version)
            self.assertEqual(0, b2_max.version)
            self.assertEqual(1, b3_max.version)

            # get versions by issue date:
            # when date precedes all bills, version should always be max
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 0,
                version=date(2011,1,1)).version)
            self.assertEqual(2, self.reebill_dao.load_reebill('99999', 1,
                version=date(2011,1,1)).version)
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 2,
                version=date(2011,1,1)).version)
            self.assertEqual(1, self.reebill_dao.load_reebill('99999', 3,
                version=date(2011,1,1)).version)
            # when date follows all bills, version should always be max
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 0,
                version=date(2013,1,1)).version)
            self.assertEqual(2, self.reebill_dao.load_reebill('99999', 1,
                version=date(2013,1,1)).version)
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 2,
                version=date(2013,1,1)).version)
            self.assertEqual(1, self.reebill_dao.load_reebill('99999', 3,
                version=date(2013,1,1)).version)
            # date between issue dates of 1-0 and 1-1
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 1,
                version=date(2012,1,15)).version)
            # date between issue dates of 1-1 and 1-2
            self.assertEqual(1, self.reebill_dao.load_reebill('99999', 1,
                version=date(2012,3,1)).version)
            # date between issue dates of 3-0 and 3-1
            self.assertEqual(0, self.reebill_dao.load_reebill('99999', 3,
                version=date(2012,4,1)).version)

            # error when reebill is not found
            self.assertRaises(NoSuchBillException,
                    self.reebill_dao.load_reebill, '10003', 1)
            self.assertRaises(NoSuchBillException,
                    self.reebill_dao.load_reebill, '99999', 10)
            self.assertRaises(NoSuchBillException,
                    self.reebill_dao.load_reebill, '99999', 1, version=5)

    def test_save_reebill(self):
        with DBSession(self.state_db) as session:
            b = example_data.get_reebill('99999', 1)
            self.reebill_dao.save_reebill(b)
            self.state_db.new_reebill(session, '99999', 1)

            # save frozen utility bills
            self.reebill_dao.save_reebill(b, freeze_utilbills=True)
            u = b._utilbills[0]
            utilbills = self.reebill_dao.load_utilbills(account='99999',
                    utility=u['utility'], service=u['service'],
                    start=u['start'], end=u['end'])
            self.assertEquals(2, len(utilbills))
            utilbills = self.reebill_dao.load_utilbills(account='99999',
                    utility=u['utility'], service=u['service'],
                    start=u['start'], end=u['end'], sequence=1)
            
            # reebill with frozen utility bills can still be saved, but it
            # can't be saved again with freeze_utilbills=True
            self.reebill_dao.save_reebill(b)
            self.assertRaises(NotUniqueException,
                    self.reebill_dao.save_reebill, b, freeze_utilbills=True)

            # save again to make sure the failed call to
            # save_reebill(freeze_utilbills=True) above did not modify
            # _id, sequence, or version
            self.reebill_dao.save_reebill(b)

            # trying to make SQLAlchemy flush its cache
            #from billing.processing.state import ReeBill
            #session.query(ReeBill).all()
            #sqlalchemy.flush()

            # issued reebill can't be saved at all
            self.state_db.issue(session, '99999', 1)
            self.assertRaises(IssuedBillError, self.reebill_dao.save_reebill,
                    b)
            self.assertRaises(IssuedBillError,
                    self.reebill_dao.save_reebill, b, freeze_utilbills=True)

    def test_load_utilbill(self):
        # template utility bill is already saved in Mongo; load it and make
        # sure it's the same as the one in example_data.
        # example_data bill must be modified to get it to match (the same type
        # conversions happen when it's loaded out of mongo too)
        ub = example_data.get_utilbill_dict(u'99999', start=date(1900,1,1),
                end=date(1900,2,1), utility=u'washgas', service=u'gas')

        self.maxDiff = None
        self.assertDocumentsEqualExceptKeys(ub,
                self.reebill_dao.load_utilbill('99999', 'gas', 'washgas',
                date(1900,1,1), date(1900,2,1)), '_id', 'chargegroups')

        # TODO more

    def test_load_utilbills(self):
        # there's 1 utility bill already in the db
        self.assertEquals(1, len(self.reebill_dao.load_utilbills()))

        # query by each _id field
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                account='99999')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                service='gas')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                utility='washgas')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                start=date(1900,01,01))))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                end=date(1900,02,01))))

        # query by everything together
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                account='99999', service='gas', utility='washgas',
                start=date(1900,01,01), end=date(1900,02,01))))

        # everything together + nonexistence of "sequence", "version"
        # (load_utilbill insists on getting exactly 1 result)
        self.reebill_dao.load_utilbill(account='99999', service='gas',
                utility='washgas', start=date(1900,01,01),
                end=date(1900,02,01), sequence=False, version=False)

        # a 2nd utility bill
        second = example_data.get_utilbill_dict('99999', start=date(2012,7,22),
                end=date(2012,8,22))
        second['service'] = 'electric'
        second['utility'] = 'washgas'
        self.reebill_dao._save_utilbill(second)
        bills = self.reebill_dao.load_utilbills()
        self.assertEquals(2, len(bills))
        first = self.reebill_dao.load_utilbills()[0]
        self.assertEquals(first, bills[0])
        self.assertEquals(second, bills[1])

        # some queries for one bill, both, none
        self.assertEquals(2, len(self.reebill_dao.load_utilbills(
                account='99999')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                account='99999', service='gas')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                service='electric')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                start=datetime(2012,7,22), end=datetime(2012,8,22))))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                end=datetime(1900,02,01))))
        self.assertEquals([], self.reebill_dao.load_utilbills(
                service='cold fusion'))

    def test_save_utilbill(self):
        # ensure that a utilbill with "sequence" or "version" keys in it can
        # only be saved once
        utilbill = example_data.get_utilbill_dict('99999')
        self.reebill_dao._save_utilbill(utilbill)

        # multiple saves are possible when the utilbill doesn't belong to a
        # utilbill
        self.reebill_dao._save_utilbill(utilbill)
        
        # put "sequence" and "version" keys in a copy of the utilbill, and save
        attached_utilbill = copy.deepcopy(utilbill)
        self.reebill_dao._save_utilbill(attached_utilbill,
                sequence_and_version=(1, 0))

        # NOTE attached_utilbill is still saveable
        self.reebill_dao._save_utilbill(attached_utilbill)

        # and so is the original utilbill
        self.reebill_dao._save_utilbill(utilbill)

        # it should never be possible to save a utilbill with the same
        # account, utility, service, start, end as another
        other_utilbill = example_data.get_utilbill_dict('99999',
                start=utilbill['start'], end=utilbill['end'],
                service=utilbill['service'], utility=utilbill['utility'])
        self.assertRaises(NotUniqueException, self.reebill_dao._save_utilbill,
                other_utilbill)

    def test_delete_reebill(self):
        '''Tests deleting an unissued reebill document, which has no frozen
        utility bill documents associated with it.'''
        # save reebill (with utility bills)
        b = example_data.get_reebill('99999', 1)
        self.reebill_dao.save_reebill(b)

        # reebill and utility bills should be in mongo. there are 2 utility
        # bills because of the template document that is already there.
        all_reebills = self.reebill_dao.load_reebills_in_period('99999',
                version=0)
        all_utilbill_docs = self.reebill_dao.load_utilbills(
                account='99999')
        self.assertEquals(1, len(all_reebills))
        self.assertEquals(2, len(all_utilbill_docs))

        # delete reebill
        # (ReeBillDao.delete_reebill requires a state.ReeBill object so
        # pretend)
        class AnObject(object): pass
        reebill = AnObject()
        reebill.customer = AnObject()
        reebill.customer.account = '99999'
        reebill.sequence = 1
        reebill.version = 0
        self.reebill_dao.delete_reebill(reebill)

        # reebill should be gone, and utilbills should not.
        all_reebills = self.reebill_dao.load_reebills_in_period('99999',
                version=0)
        all_utilbill_docs = self.reebill_dao.load_utilbills(
                account='99999')
        self.assertEquals(0, len(all_reebills))
        self.assertEquals(2, len(all_utilbill_docs)) # includes template
        self.assertEquals(ObjectId('000000000000000000000001'),
                all_utilbill_docs[0]['_id'])

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
