'''Miscellaneous code used by test cases.'''
import unittest
from datetime import date, datetime, timedelta

class TestCase(unittest.TestCase):
    '''Extra assert methods.'''

    def assertDatetimesClose(self, d1, d2, seconds=10):
        '''Asserts that datetimes d1 and d2 differ by less than 'seconds' seconds.'''
        self.assertLess(abs(d1 - d2), timedelta(seconds=seconds))

    def assertDictMatch(self, d1, d2):
        '''Asserts that the two dictionaries are the same, up to str/unicode
        difference in strings and datetimes may only be close.'''
        self.assertEqual(sorted(d1.keys()), sorted(d2.keys()))
        for k, v in d1.iteritems():
            self.assertTrue(k in d2)
            v2 = d2[k]
            if type(v) is datetime and type(v2) is datetime:
                self.assertDatetimesClose(v, v2)
            else:
                self.assertEquals(v, v2)

