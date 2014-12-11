'''Integration tests for receiving data associated with an existing utility
bill file over AMQP. The RabbitMQ server is not started by this test so it
must be running separately before the test starts.
'''
from StringIO import StringIO
import json

import pika
from pika.exceptions import ChannelClosed

from billing.core.amqp_exchange import BillingHandler, ConsumeUtilityGuidHandler
from billing.core.model import Session, Utility
from billing.core.utilbill_loader import UtilBillLoader
from billing.core.altitude import AltitudeUtility, AltitudeGUID
from billing.test.setup_teardown import TestCaseWithSetup
from billing import config
from billing.exc import DuplicateFileError


class TestUploadBillAMQP(TestCaseWithSetup):

    def _queue_exists(self):
        '''Return True if the queue named by 'self.queue_name' exists,
        False otherwise.
        '''
        # for an unknown reason, queue_declare() can cause the channel used
        # to become closed, so a separate channel must be used for this
        tmp_channel = self.connection.channel()

        # "passive declare" of the queue will fail if the queue does not
        # exist and otherwise do nothing, so is equivalent to checking if the
        # queue exists
        try:
            tmp_channel.queue_declare(queue=self.queue_name, passive=True)
        except ChannelClosed:
            result = False
        else:
            result = True

        if tmp_channel.is_open:
            tmp_channel.close()
        return result

    def _clean_up_rabbitmq(self):
           if self._queue_exists():
                self.channel.queue_purge(queue=self.queue_name)

                # TODO: the queue cannot be deleted because pika raises
                # 'ConsumerCancelled' here for an unknown reason. this seems
                # similar to this Github issue from 2012 that is described as
                # "correct behavior":
                # https://github.com/pika/pika/issues/223
                # self.channel.queue_delete(queue=self.queue_name)

    def setUp(self):
        super(TestUploadBillAMQP, self).setUp()

        host_name = config.get('amqp', 'host')
        self.exchange_name = config.get('amqp', 'exchange')
        self.queue_name = config.get('amqp', 'utilbill_queue')

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host_name))
        self.channel = self.connection.channel()
        self._clean_up_rabbitmq()
        self.channel.exchange_declare(exchange=self.exchange_name)
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_bind(exchange=self.exchange_name,
                                queue=self.queue_name)

        self.utilbill_loader = UtilBillLoader(Session())

    def tearDown(self):
        self._clean_up_rabbitmq()
        self.connection.close()
        super(self.__class__, self).tearDown()

    def test_upload_bill_amqp(self):
        # put the file in place
        the_file = StringIO('test data')
        file_hash = self.utilbill_processor.bill_file_handler.upload_file(
            the_file)

        # no UtilBills exist yet with this hash
        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        # altitude GUID entities must exist
        s = Session()
        utility = s.query(Utility).first()
        guid_a, guid_b = 'A' * AltitudeGUID.LENGTH, 'B' * AltitudeGUID.LENGTH
        s.add_all([AltitudeUtility(utility, guid_a),
                   AltitudeUtility(utility, guid_b),
                   ])

        # two messages with the same sha256_hexigest: the first one will
        # cause a UtilBill to be created, but the second will cause a
        # DuplicateFileError to be raised.
        message1 = json.dumps(dict(
            utility_account_number='1',
            utility_provider_guid=guid_a,
            sha256_hexdigest=file_hash,
            # due_date='2014-09-30T18:00:00+00:00',
            total='$231.12',
            service_address='123 Hollywood Drive'))
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message1)
        message2 = json.dumps(dict(
            utility_account_number='2',
            utility_provider_guid=guid_b,
            sha256_hexdigest=file_hash,
            # due_date='2014-09-30T18:00:00+00:00',
            total='',
            service_address=''))
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message2)

        # receive message: this not only causes the callback function to be
        # registered, but also calls it for any messages that are already
        # present when it is registered. any messages that are inserted after
        # "basic_consume" is called will not be processed until after the
        # test is finished, so we can't check for them.
        with self.assertRaises(DuplicateFileError):
            consume_utilbill_file(self.channel, self.queue_name,
                                  self.utilbill_processor)

        # make sure the data have been received. we can only check for the
        # final state after all messages have been processed, not the
        # intermediate states after receiving each individual message. that's
        # not ideal, but not a huge problem because we also have unit testing.
        self.assertEqual(1, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        # check metadata that were provided with the bill:
        u = self.utilbill_loader.get_last_real_utilbill('99999')
        #self.assertEqual(date(2014,9,30), u.due_date)
        self.assertEqual(231.12, u.target_total)
        self.assertEqual('123 Hollywood Drive', u.service_address.street)
        self.assertEqual('', u.service_address.city)
        self.assertEqual('', u.service_address.state)
        self.assertEqual('', u.service_address.postal_code)
