'''Integration tests for receiving data associated with an existing utility
bill file over AMQP. The RabbitMQ server is not started by this test so it
must be running separately before the test starts.
'''
from StringIO import StringIO
from datetime import date
from pika import URLParameters
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm.exc import NoResultFound
from unittest import TestCase
from voluptuous import Invalid
from core import init_model
from util import FixMQ

with FixMQ():
    from core.amqp_exchange import create_dependencies, \
        ConsumeUtilbillFileHandler, TotalValidator, DueDateValidator
    from mq import IncomingMessage
    from mq.tests import create_mock_channel_method_props, \
        create_channel_message_body

from core.model import Session, UtilityAccount, Utility, Address
from core.altitude import AltitudeUtility, AltitudeGUID, AltitudeAccount
from core.utilbill_loader import UtilBillLoader
from exc import DuplicateFileError
from test import init_test_config
from test.setup_teardown import TestCaseWithSetup, FakeS3Manager, \
    create_utilbill_processor, create_reebill_objects, create_nexus_util, \
    clear_db


class TestValidators(TestCase):

    def test_total_validator(self):
        validator = TotalValidator()
        self.assertEqual(validator('$123.45'), 123.45)
        self.assertEqual(validator(''), None)
        self.assertEqual(123, validator('$123'))
        self.assertEqual(.4, validator('$.4'))
        self.assertEqual(.45, validator('$.45'))
        self.assertEqual(1234.56, validator('$1,234.56'))
        self.assertEqual(1234, validator('$1,234'))
        # commas in the wrong place are allowed
        self.assertEqual(1234, validator('$12,34'))

        # Negative dollar values are in accounting notation "($1,234.56)"
        self.assertEqual(validator('($123.45)'), -123.45)
        self.assertEqual(-123, validator('($123)'))
        self.assertEqual(-.4, validator('($.4)'))
        self.assertEqual(-.45, validator('($.45)'))
        self.assertEqual(-1234.56, validator('($1,234.56)'))
        self.assertEqual(-1234, validator('($1,234)'))
        # commas in the wrong place are allowed
        self.assertEqual(-1234, validator('($12,34)'))

        with self.assertRaises(Invalid):
            validator("nonsense")
        with self.assertRaises(Invalid):
            validator('$123.4,5')

    def test_due_date_validator(self):
        validator = DueDateValidator()
        self.assertEqual(validator('2010-07-21T23:15:12'), date(2010, 7, 21))
        self.assertEqual(validator(''), None)
        with self.assertRaises(Invalid):
            validator("nonsense")

class TestUploadBillAMQP(TestCase):
    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()

        # these objects don't change during the tests, so they should be
        # created only once.
        FakeS3Manager.start()
        cls.utilbill_processor = create_utilbill_processor()
        cls.billupload = cls.utilbill_processor.bill_file_handler
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.nexus_util = create_nexus_util()

    @classmethod
    def tearDownClass(cls):
        FakeS3Manager.stop()

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()

        # parameters for real RabbitMQ connection are stored but never used so
        # there is no actual connection
        exchange_name, routing_key, amqp_connection_parameters, \
                utilbill_processor = create_dependencies()
        self.handler = ConsumeUtilbillFileHandler(
            exchange_name, routing_key, amqp_connection_parameters,
            utilbill_processor)

        # We don't have to wait for the rabbitmq connection to close,
        # since we're never instatiating a connection
        self.handler._wait_on_close = 0

        self.utilbill_loader = self.utilbill_processor._utilbill_loader

        # these are for creating IncomingMessage objects for 'handler' to
        # handle
        _, self.mock_method, self.mock_props = \
            create_mock_channel_method_props()

    def tearDown(self):
        clear_db()

    def test_upload_bill_with_no_matching_utility_account_and_utility_amqp(self):
        # put the file in place
        the_file = StringIO('initial test data')
        file_hash = self.utilbill_processor.bill_file_handler.upload_file(
            the_file)

        the_file2 = StringIO('some test data')
        file_hash1 = self.utilbill_processor.bill_file_handler.upload_file(
            the_file2)

        # no UtilBills exist yet with this hash
        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        s = Session()
        guid = 'c59fded5-53ed-482e-8ca4-87819042e687'

        message = create_channel_message_body(dict(
            message_version=[1, 0],
            utility_account_number='45',
            utility_provider_guid=guid,
            sha256_hexdigest=file_hash,
            due_date='2014-09-30T18:00:00',
            total='$231.12',
            service_address='123 Hollywood Drive',
            account_guids=['C' * AltitudeGUID.LENGTH,
                           'D' * AltitudeGUID.LENGTH]))

        message_obj = IncomingMessage(self.mock_method, self.mock_props,
                                      message)

        # Process the message
        message_obj = self.handler.validate(message_obj)
        self.assertRaises(NoResultFound, self.handler.handle, message_obj)

        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))
        utility_account = s.query(UtilityAccount).\
            filter(UtilityAccount.account_number=='45').all()
        self.assertEqual(0, len(utility_account))

    def test_upload_bill_with_no_matching_utility_account_and_matching_utility_amqp(self):
        the_file = StringIO('some test data')
        file_hash = self.utilbill_processor.bill_file_handler.upload_file(
            the_file)

        # no UtilBills exist yet with this hash
        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        s = Session()
        guid = '9980ff2b-df6f-4a2f-8e01-e5f0a3ec09af'
        utility = Utility(name='Some Utility', address=Address())
        s.add(AltitudeUtility(utility, guid))

        message = create_channel_message_body(dict(
            message_version=[1, 0],
            utility_account_number='46',
            utility_provider_guid=guid,
            sha256_hexdigest=file_hash,
            due_date='2014-09-30T18:00:00',
            total='$231.12',
            service_address='123 Hollywood Drive',
            account_guids=['C' * AltitudeGUID.LENGTH,
                           'D' * AltitudeGUID.LENGTH]))

        message_obj = IncomingMessage(self.mock_method, self.mock_props, message)

        # Process the message
        message_obj = self.handler.validate(message_obj)
        self.handler.handle(message_obj)
        self.assertEqual(1, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))
        utility_account = s.query(UtilityAccount).\
            filter(UtilityAccount.account_number=='46').all()
        self.assertEqual(1, len(utility_account))
        self.assertEqual(None,
                         utility_account[0].fb_supplier)
        self.assertEqual(None,
                         utility_account[0].fb_rate_class)
        self.assertEqual('Some Utility',
                         utility_account[0].fb_utility.name)

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
        guid_a = '5efc8f5a-7cca-48eb-af58-7787348388c5'
        guid_b = '3e7f9bf5-f729-423c-acde-58f6174df551'
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

        # Process the first message
        message_obj = self.handler.validate(message_obj)
        self.handler.handle(message_obj)

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

        # Process the second message
        message_obj = self.handler.validate(message_obj)
        with self.assertRaises(DuplicateFileError):
            self.handler.handle(message_obj)

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
