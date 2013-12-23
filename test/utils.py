'''Miscellaneous code used by test cases.'''
import unittest
from datetime import date, datetime, timedelta
from copy import deepcopy

class TestCase(unittest.TestCase):
    '''Extra assert methods.'''

    def assertDecimalAlmostEqual(self, x, y, places=7):
        '''Asserts equality between any objects that can be cast to floats
        (especially Decimals) up to 'places'.'''
        self.assertAlmostEqual(float(x), float(y), places=places)

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

    def assertDocumentsEqualExceptKeys(self, d1, d2, *keys_to_exclude):
        '''Asserts that two Mongo documents (dictionaries) are the same except
        for keys in 'keys_to_exclude' (which don't necessarily have to be
        present in the documents.'''
        d1, d2 = deepcopy(d1), deepcopy(d2)
        for key in keys_to_exclude:
            for d in (d1, d2):
                if key in d:
                    del d[key]
        self.assertEqual(d1, d2)
