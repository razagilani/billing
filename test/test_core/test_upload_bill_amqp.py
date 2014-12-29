'''Integration tests for receiving data associated with an existing utility
bill file over AMQP. The RabbitMQ server is not started by this test so it
must be running separately before the test starts.
'''
from StringIO import StringIO
from datetime import date
from pika import ConnectionParameters
from datetime import datetime
from uuid import uuid4

from billing.core.model import Session, UtilityAccount
from billing.core.altitude import AltitudeUtility, AltitudeGUID, AltitudeAccount
from billing.core.utilbill_loader import UtilBillLoader
from billing.test.setup_teardown import TestCaseWithSetup
from billing.exc import DuplicateFileError
from billing.test.testing_utils import clean_up_rabbitmq
from billing.mq.tests import create_channel_message_body, create_mock_channel_method_props
from billing.mq import IncomingMessage
from billing.core.amqp_exchange import BillingHandler, ConsumeUtilbillFileHandler


class TestUploadBillAMQP(TestCaseWithSetup):

    def setUp(self):
        super(TestUploadBillAMQP, self).setUp()
        from billing import config

        _, method, props = create_mock_channel_method_props()
        self.mock_method = method
        self.mock_props = props
        self.handler = ConsumeUtilbillFileHandler(
            config.get('amqp', 'exchange'),
            config.get('amqp', 'utilbill_routing_key'),
            {},
            ConnectionParameters(host=config.get('amqp', 'host'))
        )
        # We don't have to wait for the rabbitmq connection to close,
        # since we're never instatiating a connection
        self.handler._wait_on_close = 0

        self.utilbill_loader = UtilBillLoader(Session())

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
        utility_account = s.query(UtilityAccount).filter_by(
            account='99999').one()
        utility = utility_account.fb_utility
        guid_a, guid_b = str(uuid4()), str(uuid4())
        s.add_all([AltitudeUtility(utility, guid_a),
                   AltitudeUtility(utility, guid_b),
                   ])

        # two messages with the same sha256_hexigest: the first one will
        # cause a UtilBill to be created, but the second will cause a
        # DuplicateFileError to be raised. the second message also checks the
        # "empty" values that are allowed for some fields in the message.
        message1 = create_channel_message_body(dict(
            message_version=[1, 0],
            utility_account_number='1',
            utility_provider_guid=guid_a,
            sha256_hexdigest=file_hash,
            due_date='2014-09-30T18:00:00',
            total='$231.12',
            service_address='123 Hollywood Drive',
            account_guids=['C' * AltitudeGUID.LENGTH,
                           'D' * AltitudeGUID.LENGTH]))
        message_obj = IncomingMessage(self.mock_method, self.mock_props, message1)
        self.handler.message_queue.put(message_obj)

        # Process the first message
        self.handler._handle_wrapper()

        message2 = create_channel_message_body(dict(
            message_version=[1, 0],
            utility_account_number='2',
            utility_provider_guid=guid_b,
            sha256_hexdigest=file_hash,
            due_date='',
            total='',
            service_address='',
            account_guids=[]))
        message_obj = IncomingMessage(self.mock_method, self.mock_props,
                                      message2)
        self.handler.message_queue.put(message_obj)

        # Process the second message
        with self.assertRaises(DuplicateFileError):
            self.handler._handle_wrapper()

        # make sure the data have been received. we can only check for the
        # final state after all messages have been processed, not the
        # intermediate states after receiving each individual message. that's
        # not ideal, but not a huge problem because we also have unit testing.
        self.assertEqual(1, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        # check metadata that were provided with the bill:
        u = self.utilbill_loader.get_last_real_utilbill(utility_account.account)
        self.assertEqual(date(2014, 9, 30), u.due_date)
        self.assertEqual(231.12, u.target_total)
        self.assertEqual('123 Hollywood Drive', u.service_address.street)
        self.assertEqual('', u.service_address.city)
        self.assertEqual('', u.service_address.state)
        self.assertEqual('', u.service_address.postal_code)

        altitude_accounts = s.query(AltitudeAccount).all()
        self.assertEqual(2, len(altitude_accounts))
        for aa in altitude_accounts:
            self.assertEqual(utility_account, aa.utility_account)
