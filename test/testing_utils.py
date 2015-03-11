'''Miscellaneous code used by test cases.'''
import unittest
from datetime import date, datetime, timedelta
from copy import deepcopy
from pika.exceptions import ChannelClosed


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
        # compare lists elementwise
        if isinstance(d1, list) and isinstance(d2, list) \
                and len(d1) == len(d2):
            for a, b in zip(d1, d2):
                self.assertDocumentsEqualExceptKeys(a, b, *keys_to_exclude)
            return

        # regular dictionaries
        d1, d2 = deepcopy(d1), deepcopy(d2)
        for key in keys_to_exclude:
            for d in (d1, d2):
                if isinstance(key, list):
                    k = tuple(key)
                else:
                    k = key
                if k in d:
                    del d[key]
        self.assertEqual(d1, d2)

def _rabbitmq_queue_exists(connection, queue_name):
    '''Return True if the queue named by 'self.queue_name' exists,
    False otherwise.
    '''
    # for an unknown reason, queue_declare() can cause the channel used
    # to become closed, so a separate channel must be used for this
    tmp_channel = connection.channel()

    # "passive declare" of the queue will fail if the queue does not
    # exist and otherwise do nothing, so is equivalent to checking if the
    # queue exists
    try:
        tmp_channel.queue_declare(queue=queue_name, passive=True)
    except ChannelClosed:
        result = False
    else:
        result = True

    if tmp_channel.is_open:
        tmp_channel.close()
    return result

def clean_up_rabbitmq(connection, queue_name):
    '''Clear out messages to reset the given queue to its original state.
    Should be run before and after tests that use RabbitMQ.
    :param connection: pika.connection.Connection
    :param queue_name: name of queue to clean up (string)
    '''
    tmp_channel = connection.channel()
    if _rabbitmq_queue_exists(connection, queue_name):
        tmp_channel.queue_purge(queue=queue_name)

        # TODO: the queue cannot be deleted because pika raises
        # 'ConsumerCancelled' here for an unknown reason. this seems
        # similar to this Github issue from 2012 that is described as
        # "correct behavior":
        # https://github.com/pika/pika/issues/223
        # self.channel.queue_delete(queue=self.queue_name)

