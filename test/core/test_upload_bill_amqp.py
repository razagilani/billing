from StringIO import StringIO
import json

import pika
from pika.exceptions import ChannelClosed

from billing.core.amqp_exchange import run
from billing.core.model import Session, UtilBillLoader
from billing.test.setup_teardown import TestCaseWithSetup
from billing import config


class TestUploadBillAMQP(TestCaseWithSetup):
    '''Integration test for receiving data associated with an existing utility
    bill file over AMQP. The RabbitMQ server is not started by this test so
    it must be running in order for this to work.
    '''

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
        self.queue_name = config.get('amqp', 'queue')

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host_name))
        self.channel = self.connection.channel()
        self._clean_up_rabbitmq()
        self.channel.exchange_declare(exchange=self.exchange_name)
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_bind(exchange=self.exchange_name,
                                queue=self.queue_name)

        # TODO: replace with just a UtilBillProcessor (BILL-5776)
        self.utilbill_processor = self.process

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

        # send message
        message = json.dumps({'account': '99999','utility_guid': 'a',
                              'sha256_hexdigest': file_hash})
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message)

        # receive message
        run(self.channel, self.queue_name, self.utilbill_processor)

        # make sure the data have been received
        self.assertEqual(1, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))
