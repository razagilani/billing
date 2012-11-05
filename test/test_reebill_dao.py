#!/usr/bin/python
import unittest
import pymongo
import sqlalchemy
import copy
from datetime import date, datetime, timedelta
from billing.util import dateutils
from billing.processing import mongo
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
import MySQLdb
from billing.test import example_data
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.mongo import NoSuchBillException, IssuedBillError, NotUniqueException
from billing.processing.session_contextmanager import DBSession

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillDAOTest(TestCaseWithSetup):
    def test_load_reebill(self):
        with DBSession(self.state_db) as session:
            # put some reebills in Mongo, including non-0 versions
            b0 = example_data.get_reebill('99999', 0, start=date(2012,1,1), end=date(2012,2,1), version=0)
            b1 = example_data.get_reebill('99999', 1, start=date(2012,2,1), end=date(2012,3,1), version=0)
            b1_1 = example_data.get_reebill('99999', 1, start=date(2012,2,1), end=date(2012,3,1), version=1)
            b1_2 = example_data.get_reebill('99999', 1, start=date(2012,2,1), end=date(2012,3,1), version=2)
            b2 = example_data.get_reebill('99999', 2, start=date(2012,3,1), end=date(2012,4,1), version=0)
            b3 = example_data.get_reebill('99999', 3, start=date(2012,4,1), end=date(2012,5,1), version=0)
            b3_1 = example_data.get_reebill('99999', 3, start=date(2012,4,1), end=date(2012,5,1), version=1)

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

            # save reebill docs in Mongo, and add rows in MySQL with max
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
            self.state_db.new_rebill(session, '99999', 1, max_version=2)
            self.state_db.new_rebill(session, '99999', 2, max_version=0)
            self.state_db.new_rebill(session, '99999', 3, max_version=1)

            # freezing of utililty bills should have created one one frozen
            # copy for each issued reebill (3) in addition to the editable one
            # for each sequence (4), for a total of 7
            all_utilbill_docs = self.reebill_dao.load_utilbills(account='99999')
            self.assertEquals(7, len(all_utilbill_docs))

            # with no extra args to load_reebill(), maximum version should come out
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
            self.state_db.new_rebill(session, '99999', 1)

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
            #from billing.processing.db_objects import ReeBill
            #session.query(ReeBill).all()
            #sqlalchemy.flush()

            # issued reebill can't be saved at all
            self.state_db.issue(session, '99999', 1)
            self.assertRaises(IssuedBillError, self.reebill_dao.save_reebill,
                    b)
            self.assertRaises(NotUniqueException,
                    self.reebill_dao.save_reebill, b, freeze_utilbills=True)

    def test_load_utilbill(self):
        # nothing to load
        self.assertRaises(NoSuchBillException,
                self.reebill_dao.load_utilbill, '99999', 'gas', 'washgas',
                date(2012,11,12), date(2012,12,14))

        # save a utilbill
        ub = example_data.get_utilbill_dict('99999')
        self.reebill_dao._save_utilbill(ub)

        # load it
        self.assertEqual(ub, self.reebill_dao.load_utilbill('99999', 'gas',
                'washgas', date(2011,11,12), date(2011,12,14)))

        # TODO more

    def test_load_utilbills(self):
        # no utility bills
        self.assertEqual([], self.reebill_dao.load_utilbills())

        # 1 utility bill
        first = example_data.get_utilbill_dict('99999')
        self.reebill_dao._save_utilbill(first)
        self.assertEquals(1, len(self.reebill_dao.load_utilbills()))

        # query by each _id field
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                account='99999')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                service='gas')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                utility='washgas')))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                start=date(2011,11,12))))
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                end=date(2011,12,14))))

        # query by everything together
        self.assertEquals(1, len(self.reebill_dao.load_utilbills(
                account='99999', service='gas', utility='washgas',
                start=date(2011,11,12), end=date(2011,12,14))))

        # everything together + nonexistence of "sequence", "version"
        # (load_utilbill insists on getting exactly 1 result)
        self.reebill_dao.load_utilbill(account='99999', service='gas',
                utility='washgas', start=date(2011,11,12),
                end=date(2011,12,14), sequence=False, version=False)

        # a 2nd utility bill
        second = example_data.get_utilbill_dict('99999', start=date(2012,7,22),
                end=date(2012,8,22))
        second['service'] = 'electric'
        second['utility'] = 'washgas'
        self.reebill_dao._save_utilbill(second)
        bills = self.reebill_dao.load_utilbills()
        self.assertEquals(2, len(bills))
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
                end=datetime(2011,12,14))))
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
        with DBSession(self.state_db) as session:
            # save reebill (with utility bills)
            b = example_data.get_reebill('99999', 1)
            self.reebill_dao.save_reebill(b)
            self.state_db.new_rebill(session, '99999', 1)

            # reebill and utility bills should be in mongo
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version=0)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            self.assertEquals(1, len(all_reebills))
            self.assertEquals(1, len(all_utilbill_docs))

            # delete
            self.reebill_dao.delete_reebill('99999', 1, 0)

            # both reebill and utilbills should be gone
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version=0)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            self.assertEquals(0, len(all_reebills))
            self.assertEquals(0, len(all_utilbill_docs))

            # save reebill and utility bills again
            b = example_data.get_reebill('99999', 1)
            self.reebill_dao.save_reebill(b)

            # if utility bill is frozen and verison == 0, both frozen utility
            # bill and editable one should be deleted
            self.reebill_dao.save_reebill(b, freeze_utilbills=True)
            self.reebill_dao.delete_reebill('99999', 1, 0)
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version=0)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            self.assertEquals(0, len(all_reebills))
            self.assertEquals(0, len(all_utilbill_docs))

            # if utility bill is frozen and version > 0, nothing should be
            # deleted
            self.state_db.issue(session, '99999', 1)
            self.state_db.increment_version(session, '99999', 1)
            correction = example_data.get_reebill('99999', 1, version=1)
            self.reebill_dao.save_reebill(correction)
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version='any', include_0=True)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            self.assertEquals(1, len(all_reebills))
            self.assertEquals(1, all_reebills[0].version)
            self.assertEquals(1, len(all_utilbill_docs))
            self.assertFalse('sequence' in all_utilbill_docs[0])
            self.assertFalse('version' in all_utilbill_docs[0])

            # if utility bill is frozen and version > 0, frozen utility
            # bill should be deleted but editable one should not
            self.reebill_dao.save_reebill(correction, freeze_utilbills=True)
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version='any', include_0=True)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            assert len(all_reebills) == 1
            assert len(all_utilbill_docs) == 2
            self.reebill_dao.delete_reebill('99999', 1, 1)
            all_reebills = self.reebill_dao.load_reebills_in_period('99999', version='any', include_0=True)
            all_utilbill_docs = self.reebill_dao.load_utilbills('99999')
            self.assertEquals(0, len(all_reebills))
            self.assertEquals(1, len(all_utilbill_docs))
            self.assertFalse('sequence' in all_utilbill_docs[0])
            self.assertFalse('version' in all_utilbill_docs[0])

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
