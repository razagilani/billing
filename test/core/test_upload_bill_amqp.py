'''Integration tests for receiving data associated with an existing utility
bill file over AMQP. The RabbitMQ server is not started by this test so it
must be running separately before the test starts.
'''
from StringIO import StringIO
import json
from formencode import Invalid

import pika
from pika.exceptions import ChannelClosed

from billing.core.amqp_exchange import consume_utilbill_file
from billing.core.model import Session, UtilBillLoader, UtilityAccount
from billing.core.altitude import AltitudeUtility, AltitudeGUID, AltitudeAccount
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

        # put the file in place
        self.file = StringIO('test data')
        self.file_hash = self.utilbill_processor.bill_file_handler.upload_file(
            self.file)

        # altitude GUID entities must exist
        s = Session()
        self.utility_account = s.query(UtilityAccount).filter_by(
            account='99999').one()
        self.utility = self.utility_account.fb_utility
        self.guid_a = 'A' * AltitudeGUID.LENGTH
        self.guid_b = 'B' * AltitudeGUID.LENGTH
        s.add_all([AltitudeUtility(self.utility, self.guid_a),
                   AltitudeUtility(self.utility, self.guid_b),
                   ])

    def tearDown(self):
        self._clean_up_rabbitmq()
        self.connection.close()
        super(self.__class__, self).tearDown()

    def test_basic(self):
        # no UtilBills exist yet with this hash
        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            self.file_hash))

        # two messages with the same sha256_hexigest: the first one will
        # cause a UtilBill to be created, but the second will cause a
        # DuplicateFileError to be raised. the second message also checks the
        # "empty" values that are allowed for some fields in the message.
        message1 = json.dumps(dict(
            message_version=[1, 0],
            utility_account_number='1',
            utility_provider_guid=self.guid_a,
            sha256_hexdigest=self.file_hash,
            # due_date='2014-09-30T18:00:00+00:00',
            total='$231.12',
            service_address='123 Hollywood Drive',
            account_guids=['C' * AltitudeGUID.LENGTH,
                           'D' * AltitudeGUID.LENGTH]))
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message1)
        message2 = json.dumps(dict(
            message_version=[1, 0],
            utility_account_number='2',
            utility_provider_guid=self.guid_b,
            sha256_hexdigest=self.file_hash,
            # due_date='2014-09-30T18:00:00+00:00',
            total='',
            service_address='',
            account_guids=[]))
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
            self.file_hash))

        # check metadata that were provided with the bill:
        u = self.utilbill_loader.get_last_real_utilbill(
            self.utility_account.account)
        #self.assertEqual(date(2014,9,30), u.due_date)
        self.assertEqual(231.12, u.target_total)
        self.assertEqual('123 Hollywood Drive', u.service_address.street)
        self.assertEqual('', u.service_address.city)
        self.assertEqual('', u.service_address.state)
        self.assertEqual('', u.service_address.postal_code)

        altitude_accounts = Session().query(AltitudeAccount).all()
        self.assertEqual(2, len(altitude_accounts))
        for aa in altitude_accounts:
            self.assertEqual(self.utility_account, aa.utility_account)

    def test_invalid_message(self):
        # TODO: this might be better as a unit test
        valid_message = dict(
            message_version=[1, 0],
            utility_account_number='1',
            utility_provider_guid=self.guid_b,
            sha256_hexdigest=self.file_hash,
            # due_date='2014-09-30T18:00:00+00:00',
            total='',
            service_address='',
            account_guids=[])
        for invalid_message in [
            dict(valid_message, message_version=[1, 1]),
            dict(valid_message, utility_account_number=1),
            dict(valid_message, utility_provider_guid='invalid guid'),
            dict(valid_message, sha256_hexdigest='abcdefg'),
            dict(valid_message, total='1.23'),
            dict(valid_message, total='$1.234'),
            dict(valid_message, total='$1.23 '),
            dict(valid_message, total=1.23),
            dict(valid_message, service_address=5),
            dict(valid_message, account_guids=['abc']),
            dict(valid_message, account_guids=[1]),
        ]:
            self.channel.basic_publish(exchange=self.exchange_name,
                                       routing_key=self.queue_name,
                                       body=json.dumps(invalid_message))
            with self.assertRaises(Invalid):
                consume_utilbill_file(self.channel, self.queue_name,
                                      self.utilbill_processor)

    # TODO:
    # check updating altitude_utility.utility_account_id when utility bill
    # messages are sent for two different accounts with the same account_guids