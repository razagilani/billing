from datetime import datetime

from brokerage.quote_parsers import DirectEnergyMatrixParser

# this must be imported to get the "quotes" fixture passed as as argument to
# the test method below
from test.test_brokerage.test_quote_parsers import quotes


# these variables are accessed inside the "quotes" fixture function
FILE_NAME = 'Matrix 1 Example - Direct Energy.xls'
ALIASES = ['Direct-electric-CT-CLP-37, R35--']
PARSER_CLASS = DirectEnergyMatrixParser
EXPECTED_COUNT = 106554

def test_direct_energy(quotes):
    q = quotes[0]
    assert q.start_from == datetime(2015, 5, 1)
    assert q.start_until == datetime(2015, 6, 1)
    assert q.term_months == 6
    assert q.valid_from == datetime(2015, 5, 4)
    assert q.valid_until == datetime(2015, 5, 5)
    assert q.min_volume == 0
    assert q.limit_volume == 75000
    assert q.rate_class_alias == ALIASES[0]
    assert q.rate_class_id == 1
    assert q.purchase_of_receivables == False
    assert q.price == .07036
