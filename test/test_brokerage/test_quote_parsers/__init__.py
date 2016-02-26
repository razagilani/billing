"""This module contains tests for individual QuoteParser subclasses. Each
test is based on an example file in the "quote_files" directory.
"""
from collections import defaultdict
from datetime import datetime
from os.path import join

from mock import Mock
from pytest import fixture

from core import ROOT_PATH


DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')

@fixture(scope='function')
def quotes(request):
    # this mock replaces the brokerage.brokerate_model module to avoid
    # accessing the database
    dao = Mock()
    dao.load_rate_class_aliases = Mock(return_value=defaultdict(lambda: [1]))

    parser = request.module.PARSER_CLASS(brokerage_dao=dao)
    with open(join(DIRECTORY, request.module.FILE_NAME), 'rb') as spreadsheet:
        parser.load_file(spreadsheet)

    assert parser.get_count() == 0
    quote_list = list(parser.extract_quotes())

    # TODO: maybe this code belongs in an actual test method
    assert parser.get_count() == request.module.EXPECTED_COUNT
    assert len(quote_list) == request.module.EXPECTED_COUNT
    for quote in quote_list:
        quote.validate()
        assert quote.date_received.date() == datetime.utcnow().date()
    return quote_list

