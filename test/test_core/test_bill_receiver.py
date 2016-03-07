"""Tests for a script that uses an HTTP API to check for utility bills and
download their metadata."""
from unittest import skip

import pytest
import requests
#from core.bill_receiver import BillReceiver
from mock import Mock, call, create_autospec

from core.utilbill_processor import UtilbillProcessor

HASH_1 = '0123456789abcdef'
HASH_2 = 'fedcba9876543210'

@pytest.fixture
def requests_module():
    requests_module = create_autospec(requests)
    response = create_autospec(requests.models.Response)
    response.json.return_value = [
        dict(utility_account_id=1,
             utility_bill_id=111,
             sha256_hexdigest=HASH_1,
             period_start='2000-01-01T00:00:00Z',
             period_end='2000-02-01T00:00:00Z'),
        dict(utility_account_id=2,
             utility_bill_id=222,
             sha256_hexdigest=HASH_2,
             period_start='2000-01-02T00:00:00Z',
             period_end='2000-02-02T00:00:00Z'),
    ]
    requests_module.get.return_value = response

@pytest.fixture
def utilbill_processor():
    return create_autospec(UtilbillProcessor)

@pytest.fixture
def bill_receiver(requests_module, utilbill_processor):
    # mock for the requests module that can be used to make HTTP requests
    return BillReceiver('http://example.com/', utilbill_processor)

@skip("this feature has not been merged into default yet ")
def test_receive_bill_simple(requests_module, utilbill_processor,
                             bill_receiver):
    bill_receiver.get_new_bills()

    # HTTP requests were made to find out about new bills
    requests_module.assert_has_calls([
        call('get', data=[dict(utility_account_id=1,
                               last_received_date='2000-03-01T00:00:00Z')]),
        call('get', data=[dict(utility_account_id=2,
                               last_received_date='2000-03-02T00:00:00Z')]),
    ])

    # new bills were inserted into database
    # TODO: determine utility account objects to put here (instead of None)
    utilbill_processor.create_utility_bill_with_existing_file.assert_has_calls([
        call(None, '0123456789abcdef'),
        call(None, 'fedcba987654321'),
    ])
