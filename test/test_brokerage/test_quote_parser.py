from datetime import datetime
from os.path import join
import re
from unittest import TestCase
from mock import Mock

from brokerage.brokerage_model import RateClass, RateClassAlias
from brokerage.quote_parser import QuoteParser, SpreadsheetReader
from core import ROOT_PATH, init_altitude_db, init_model
from brokerage.quote_parsers import (
    DirectEnergyMatrixParser, USGEMatrixParser, AEPMatrixParser,
    AmerigreenMatrixParser, ChampionMatrixParser,
    ConstellationMatrixParser, EntrustMatrixParser,
    MajorEnergyMatrixParser, SFEMatrixParser)
from core.model import AltitudeSession
from test import create_tables, init_test_config, clear_db
from util.units import unit_registry


def setUpModule():
    init_test_config()

class QuoteParserTest(TestCase):
    def setUp(self):
        reader = Mock(autospec=SpreadsheetReader)
        class ExampleQuoteParser(QuoteParser):
            def __init__(self):
                super(ExampleQuoteParser, self).__init__()
                self._reader = reader
            def _load_rate_class_aliases(self):
                # avoid use of database in this test by overriding this methof
                # where a database query is made. TODO better way to do this
                return []
            def _extract_quotes(self):
                pass
        self.qp = ExampleQuoteParser()
        self.qp.EXPECTED_ENERGY_UNIT = unit_registry.MWh
        self.qp.TARGET_ENERGY_UNIT = unit_registry.kWh
        self.reader = reader
        self.regex = re.compile(r'from (?P<low>\d+) to (?P<high>\d+)')

    def test_extract_volume_range_normal(self):
        self.reader.get_matches.return_value = 1, 2
        low, high = self.qp._extract_volume_range(0, 0, 0, self.regex)
        self.assertEqual((1000, 2000), (low, high))
        self.reader.get_matches.assert_called_once_with(0, 0, 0, self.regex,
                                                        (int, int))

    def test_extract_volume_range_fudge(self):
        self.reader.get_matches.return_value = 11, 20
        low, high = self.qp._extract_volume_range(
            0, 0, 0, self.regex, fudge_low=True, fudge_high=True)
        self.assertEqual((10000, 20000), (low, high))
        self.reader.get_matches.assert_called_once_with(0, 0, 0, self.regex,
                                                        (int, int))

        self.reader.reset_mock()
        self.reader.get_matches.return_value = 10, 19
        low, high = self.qp._extract_volume_range(
            0, 0, 0, self.regex, fudge_low=True, fudge_high=True)
        self.assertEqual((10000, 20000), (low, high))
        self.reader.get_matches.assert_called_once_with(0, 0, 0, self.regex,
                                                        (int, int))

class MatrixQuoteParsersTest(TestCase):
    # paths to example spreadsheet files from each supplier
    DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')
    AEP_FILE_PATH = join(DIRECTORY, 'AEP Energy Matrix 3.0 2015-07-21.xls')
    DIRECT_ENERGY_FILE_PATH = join(DIRECTORY,
                                   'Matrix 1 Example - Direct Energy.xls')
    USGE_FILE_PATH = join(DIRECTORY, 'Matrix 2a Example - USGE.xlsx')
    CHAMPION_FILE_PATH = join(DIRECTORY,'Matrix 4 Example - Champion.xls')
    # using version of the file converted to XLS because we can't currently
    # read the newer format
    AMERIGREEN_FILE_PATH = join(
        DIRECTORY, 'Amerigreen Matrix 08-03-2015 converted.xls')
    CONSTELLATION_FILE_PATH = join(DIRECTORY,
                                   'Matrix 5 Example - Constellation.xlsx')
    SFE_FILE_PATH = join(DIRECTORY, 'SFE Pricing Worksheet - Sep 9 2015.xlsx')
    MAJOR_FILE_PATH = join(
        DIRECTORY, 'Major Energy - Commercial and Residential Electric and '
                   'Gas Rack Rates September 21 2015.xlsx')
    ENTRUST_FILE_PATH = join(DIRECTORY, 'Matrix 10 Entrust.xlsx')

    @classmethod
    def setUpClass(cls):
        create_tables()
        init_model()
        init_altitude_db()

    def setUp(self):
        clear_db()

        self.rate_class = RateClass(rate_class_id=1)

        # TODO: it would be better to mock 'get_rate_class_for_alias' than
        # actually try to create a RateClassAlias for every one that might be
        # checked in a test
        aliases = [
            # Direct Energy
            'CT-CLP-37, R35',
            # USGE
            'Columbia of Kentucky-Residential-Residential',
            # AEP
            'DC-PEPCO_DC-GS-GSLV ND, GS LV, GS 3A',
            # Champion
            'PA-DQE-GS-General Service',
            # Amerigreen
            'NY-Con Ed',
            # Constellation
            'CLP',
            # Major Energy
            'electric-NY-CenHud-G - Hud Vil',
            'gas-NY-RGE',
            # SFE
            'A (NiMo, NYSEG)',
            # Entrust
            'Com Ed', 'ConEd Zone J',
        ]
        session = AltitudeSession()
        session.add(self.rate_class)
        session.flush()
        session.add_all(
            [RateClassAlias(rate_class_id=self.rate_class.rate_class_id,
                             rate_class_alias=a) for a in aliases])
        session.flush()

    def tearDown(self):
        clear_db()

    def test_direct_energy(self):
        parser = DirectEnergyMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.DIRECT_ENERGY_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(106554, len(quotes))
        self.assertEqual(106554, parser.get_count())
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2015, 5, 1), q1.start_from)
        self.assertEqual(datetime(2015, 6, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(75000, q1.limit_volume)
        self.assertEqual('CT-CLP-37, R35', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.07036, q1.price)

    def test_usge(self):
        parser = USGEMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.USGE_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()

        assert self.rate_class.rate_class_id == 1
        quotes = list(parser.extract_quotes())
        self.assertEqual(2448, len(quotes))

        for quote in quotes:
            quote.validate()

        # each state has its own sheet. to make sure each sheet is done
        # correctly, we check the first one in each (we determined the index
        # of each one by counting the number of quotes in each sheet)

        # KY check
        q1 = quotes[0]
        self.assertEqual('Columbia of Kentucky-Residential-Residential', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.4729, q1.price)

        # MD check
        q1 = quotes[96]
        self.assertEqual('Baltimore Gas & Electric-Residential-Residential', q1.rate_class_alias)
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.4793, q1.price)

        # NJ check
        q1 = quotes[288]
        #self.assertEqual('Residential', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(datetime(2015, 7, 1), q1.start_from)
        self.assertEqual(datetime(2015, 8, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.5242, q1.price)

        # NY check
        q1 = quotes[528]
        #self.assertEqual('Residential', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.6292, q1.price)

        # OH check
        q1 = quotes[1776]
        #self.assertEqual('Residential', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.5630, q1.price)

        # PA check
        q1 = quotes[1968]
        #self.assertEqual('Residential', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 5, 4), q1.valid_from)
        self.assertEqual(datetime(2015, 5, 5), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.4621, q1.price)

    def test_aep(self):
        parser = AEPMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.AEP_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(6664, len(quotes))
        self.assertEqual(6664, parser.get_count())
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2015, 8, 1), q1.start_from)
        self.assertEqual(datetime(2015, 9, 1), q1.start_until)
        self.assertEqual(12, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 7, 21), q1.valid_from)
        self.assertEqual(datetime(2015, 7, 22), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(100, q1.limit_volume)
        self.assertEqual('DC-PEPCO_DC-GS-GSLV ND, GS LV, GS 3A', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.08688419193651578, q1.price)

    def test_Champion(self):
        parser = ChampionMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.CHAMPION_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(3780, len(quotes))

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2015, 6, 1), q1.start_from)
        self.assertEqual(datetime(2015, 7, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(12, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(100000, q1.limit_volume)
        self.assertEqual('PA-DQE-GS-General Service', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.07686, q1.price)

    def test_amerigreen(self):
        parser = AmerigreenMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.AMERIGREEN_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet,
                             file_name='Amerigreen Matrix 08-03-2015.xlsx')
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(96, len(quotes))
        self.assertEqual(96, parser.get_count())
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2015, 9, 1), q1.start_from)
        self.assertEqual(datetime(2015, 9, 2), q1.start_until)
        self.assertEqual(3, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        # quote validity dates come from file name
        self.assertEqual(datetime(2015, 8, 3), q1.valid_from)
        self.assertEqual(datetime(2015, 8, 4), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(50000, q1.limit_volume)
        self.assertEqual('NY-Con Ed', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.34025833996486833, q1.price)

    def test_constellation(self):
        parser = ConstellationMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.CONSTELLATION_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(5567, len(quotes))

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2015, 9, 1), q1.start_from)
        self.assertEqual(datetime(2015, 10, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(6, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(150000, q1.limit_volume)
        self.assertEqual('CLP', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.103578, q1.price)

    def test_major_energy(self):
        parser = MajorEnergyMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.MAJOR_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        # there should be 936 rows * 4 columns of electric quotes, + 48 rows
        # * 3 columns - 20 blank cells = 136 gas quotes
        self.assertEqual(3868, len(quotes))

        for quote in quotes:
            quote.validate()

        # first quote is electric
        q = quotes[0]
        self.assertEqual(datetime(2015, 9, 21), q.valid_from)
        self.assertEqual(datetime(2015, 10, 7), q.valid_until)
        self.assertEqual(datetime(2015, 10, 1), q.start_from)
        self.assertEqual(datetime(2015, 11, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(74000, q.limit_volume)
        self.assertEqual('electric-NY-CenHud-G - Hud Vil', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.0878, q.price)

        # last quote is gas
        q = quotes[-1]
        self.assertEqual(datetime(2015, 9, 21), q.valid_from)
        self.assertEqual(datetime(2015, 10, 7), q.valid_until)
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(24, q.term_months)
        self.assertEqual(None, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual('gas-NY-RGE', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.3918, q.price)


    def test_sfe(self):
        parser = SFEMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.SFE_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet,
            file_name='SFE Pricing Worksheet - Sep 8 2015')
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(4350, len(quotes))

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2015, 10, 1), q1.start_from)
        self.assertEqual(datetime(2015, 11, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(6, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(150000, q1.limit_volume)
        self.assertEqual('A (NiMo, NYSEG)', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.0678491858390411, q1.price)
        
    def test_entrust(self):
        parser = EntrustMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.ENTRUST_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        # 26 sheets * 4 tables * 5 columns (of prices) * 6 rows
        self.assertEqual(3120, len(quotes))

        for quote in quotes:
            quote.validate()

        q = quotes[0]
        self.assertEqual(datetime(2015, 9, 1), q.start_from)
        self.assertEqual(datetime(2015, 10, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(12, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(15000, q.limit_volume)
        self.assertEqual('Com Ed', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.08121965893896807, q.price)

        # since this one is especially complicated and also missed a row,
        # check the last quote too. (this also checks the "sweet spot"
        # columns which work differently from the other ones)
        q = quotes[-1]
        self.assertEqual(datetime(2016, 2, 1), q.start_from)
        self.assertEqual(datetime(2016, 3, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(17, q.term_months)
        self.assertEqual(3e5, q.min_volume)
        self.assertEqual(1e6, q.limit_volume)
        self.assertEqual('ConEd Zone J', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.08106865957514724, q.price)


