'''Miscellaneous code used by test cases.'''
import unittest
import urlparse
import inspect
import cherrypy
from datetime import date, datetime, timedelta
from copy import deepcopy
from pika.exceptions import ChannelClosed
from exc import TestClientRoutingError


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
        """Assert that two dictionaries of lists of dictionaries are the same
        except for certain dictionary keys.
        :param d1: dict or list of dicts
        :param d2: dict or list of dicts
        :param keys_to_exclude: keys to exclude from comparison (they don't
        necessarily have to be present in either d1 or d2).
        """
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


class ReebillRestTestClient(object):
    """ A minimal flask/django-style test client that is able to emulate
    requests made against the custom Reebill REST interface. This only works,
    against the cutom rest methods like handle_get, etc.
    because the REST methods are not directly cherrypy.expose()'d, but rather
    routed by cherrypy through RESTResource.default(). All
    methods exposed directly via cherrypy cannot be tested with this client
    """
    def __init__(self, resource_path, resource_obj):
        self.route = resource_path
        self.resource = resource_obj

    def _set_json_request_data(self, data):
        # cherrypy.request.json is a variable that normally contains the
        # parsed json request data. We're overwirting it here to 'fake' a
        # http request
        cherrypy.request.json = data

    def _get_resource_path_query_by_url(self, url):
        urlp = urlparse.urlsplit(url)

        # for consistency with the flask test client, expect urls to begin
        # with '/'
        if not urlp.path.startswith('/'):
            raise TestClientRoutingError('%s does not start with "/"' % url)

        # uses the first part of the path to route to the equally named
        # resource in ReebillWSGI. The rest of the path is passed into the
        # handler method as positional arguments. This is equivalent to
        # cherrypy's behavior
        path_parts = urlp.path[1:].split('/')
        if len(path_parts) == 0:
            raise TestClientRoutingError('You must specify a resource')
        elif path_parts[0] != self.route:
            raise TestClientRoutingError('The path %s is not equal to %s' %
                                         (path_parts[0], self.route))

        # cherrypy flattens the query string if possible (i.e. if there is
        # only one element in a parameter array)
        qs = urlparse.parse_qs(urlp.query)
        for k, v in qs.iteritems():
            if len(v) == 1:
                qs[k] = v[0]

        return path_parts[1:], qs

    def put(self, url, data=None):
        url_parts, qs = self._get_resource_path_query_by_url(url)
        self._set_json_request_data(data if data is not None else {})
        return self.resource.handle_put(*url_parts, **qs)

    def post(self, url, data=None):
        url_parts, qs = self._get_resource_path_query_by_url(url)
        self._set_json_request_data(data if data is not None else {})
        return self.resource.handle_post(*url_parts, **qs)

    def get(self, url):
        url_parts, qs = self._get_resource_path_query_by_url(url)
        return self.resource.handle_get(*url_parts, **qs)

    def delete(self, url):
        url_parts, qs = self._get_resource_path_query_by_url(url)
        self._set_json_request_data(data)
        return self.resource.handle_delete(*url_parts, **qs)
