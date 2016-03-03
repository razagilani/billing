from datetime import datetime

from brokerage.quote_parsers.gee_gas_ny import GEEGasNYParser

# this must be imported to get the "quotes" fixture passed as as argument to
# the test method below
from test.test_brokerage.test_quote_parsers import quotes


# these variables are accessed inside the "quotes" fixture function
FILE_NAME = 'NY Rack Rates_2.2.2016.pdf'
ALIASES = [
    'NGW Non-Heat SC2-1',
    'Con Edison-Heating-SC1'
] # TODO some of the spaces should be -s
PARSER_CLASS = GEEGasNYParser
EXPECTED_COUNT = 260

def test_gee_gas_ny(quotes):
    q = quotes[0]
    assert q.start_from == datetime(2016, 2, 1)
    assert q.start_until == datetime(2016, 3, 1)
    assert q.term_months == 6
    assert q.valid_from == datetime(2016, 2, 2)
    assert q.valid_until == datetime(2016, 2, 3)
    assert q.min_volume == None
    assert q.limit_volume == None
    assert q.rate_class_alias == ALIASES[0]
    assert q.rate_class_id == 1
    assert q.price == .3732

    q = quotes[-1]
    assert q.start_from == datetime(2016, 5, 1)
    assert q.start_until == datetime(2016, 6, 1)
    assert q.term_months == 11
    assert q.valid_from == datetime(2016, 2, 2)
    assert q.valid_until == datetime(2016, 2, 3)
    assert q.min_volume == None
    assert q.limit_volume == None
    assert q.price == .4673
