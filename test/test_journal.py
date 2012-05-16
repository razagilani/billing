import unittest
import pymongo
from datetime import datetime, timedelta
from billing.reebill.journal import JournalDAO, JournalEntry

class JournalTest(unittest.TestCase):

    def assertDatetimesClose(self, d1, d2):
        '''Asserts that datetimes d1 and d2 differ by less than 1 second.'''
        self.assertLess(abs(d1 - d2), timedelta(seconds=1))

    def setUp(self):
        self.database = 'test'
        self.collection = 'journal'
        self.dao = JournalDAO(database=self.database,
                collection=self.collection)

        # fake user object to create an event (just needs an
        # identifier)
        class FakeUser(object): pass
        user = FakeUser()
        setattr(user, 'identifier', 'dan')
        self.user = user

    def tearDown(self):
        # clear out database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_note(self):
        '''Logs a Note event.'''
        self.dao.log_event(self.user, JournalDAO.Note, '99999', sequence=1,
                msg='hello')

        entries = JournalEntry.objects()
        self.assertEquals(1, len(entries))
        entry = entries[0]
        now = datetime.utcnow()
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertEquals(JournalDAO.Note, entry.event)
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals('hello', entry.msg)
    
    def test_mail(self):
        self.dao.log_event(self.user, JournalDAO.ReeBillMailed, '99999',
                sequence=1, address='jwatson@skylineinnovations.com')

        entries = JournalEntry.objects()
        self.assertEquals(1, len(entries))
        entry = entries[0]
        now = datetime.utcnow()
        self.assertDatetimesClose(datetime.utcnow(), entry.date)
        self.assertEquals(self.user.identifier, entry.user)
        self.assertEquals(JournalDAO.ReeBillMailed, entry.event)
        self.assertEquals('99999', entry.account)
        self.assertEquals(1, entry.sequence)
        self.assertEquals('jwatson@skylineinnovations.com', entry.address)


if __name__ == '__main__':
    unittest.main()
