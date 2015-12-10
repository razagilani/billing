from datetime import datetime
from os.path import join, basename
import re
from unittest import TestCase, skip

from mock import Mock

from brokerage.brokerage_model import RateClass, RateClassAlias
from brokerage.quote_parser import QuoteParser, SpreadsheetReader
from core import ROOT_PATH, init_altitude_db, init_model
from brokerage.quote_parsers import (
    DirectEnergyMatrixParser, USGEMatrixParser, AEPMatrixParser, EntrustMatrixParser,
    AmerigreenMatrixParser, ChampionMatrixParser, LibertyMatrixParser,
    ConstellationMatrixParser, MajorEnergyMatrixParser, SFEMatrixParser,
    USGEElectricMatrixParser)
from core.model import AltitudeSession
from test import create_tables, init_test_config, clear_db
from util.units import unit_registry


def setUpModule():
    init_test_config()

class QuoteParserTest(TestCase):
    def setUp(self):
        reader = Mock(autospec=SpreadsheetReader)
        class ExampleQuoteParser(QuoteParser):
            NAME = 'example'
            READER_CLASS = Mock()
            def __init__(self):
                super(ExampleQuoteParser, self).__init__()
                self._reader = reader
            def _load_rate_class_aliases(self):
                # avoid use of database in this test by overriding this method
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
        self.assertEqual((10000, 20000), (low, high)    )
        self.reader.get_matches.assert_called_once_with(0, 0, 0, self.regex,
                                                        (int, int))

class MatrixQuoteParsersTest(TestCase):
    # paths to example spreadsheet files from each supplier
    DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')
    AEP_FILE_PATH = join(DIRECTORY, 'AEP Energy Matrix 3.0 2015-11-12.xls')
    DIRECT_ENERGY_FILE_PATH = join(DIRECTORY,
                                   'Matrix 1 Example - Direct Energy.xls')
    USGE_FILE_PATH = join(DIRECTORY, 'Matrix 2a Example - USGE.xlsx')
    USGE_ELECTRIC_FILE_PATH = join(DIRECTORY, 'USGE Matrix Pricing - ELEC - 20151102.xlsx')
    CHAMPION_FILE_PATH = join(DIRECTORY,'Champion MM PJM Fixed-Index-24 '
                                        'Matrix 2015-10-30.xls')
    # using version of the file converted to XLS because we can't currently
    # read the newer format
    AMERIGREEN_FILE_PATH = join(
        DIRECTORY, 'Amerigreen Matrix 08-03-2015 converted.xls')
    CONSTELLATION_FILE_PATH = join(
        DIRECTORY, 'Constellation - SMB Cost+ Matrix_Fully '
                   'Bundled_09_24_2015.xlsm')
    SFE_FILE_PATH = join(DIRECTORY, 'SFE Pricing Worksheet - Nov 30 2015.xlsx')
    MAJOR_FILE_PATH = join(
        DIRECTORY, 'Major Energy - Commercial and Residential Electric and '
                   'Gas Rack Rates October 27 2015.xlsx')
    ENTRUST_FILE_PATH = join(DIRECTORY, 'Matrix 10 Entrust.xlsx')
    LIBERTY_FILE_PATH = join(DIRECTORY, 'Liberty Power Daily Pricing for NEX ABC 2015-09-11.xls')

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
            'PA-DQE-GS-General service',
            # Amerigreen
            'NY-Con Ed',
            # Constellation
            'CT-CLP',
            'NJ-AECO',
            # liberty
            'PEPCO-DC-PEPCO-Default',
            'PEPCO-DC-PEPCO-GTLV/DMGT',
            # Major Energy
            'electric-IL-ComEd-',
            'gas-NY-RGE',
            # SFE
            'NY-A (NiMo, NYSEG)',
            'NJ-SJG ($/therm)',
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

    @skip('ignore failure until example file is added')
    def test_usge_electric(self):
        parser = USGEElectricMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.USGE_ELECTRIC_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()

        quotes = list(parser.extract_quotes())

        self.assertEqual(quotes[0].price, 0.1017)
        self.assertEqual(quotes[0].min_volume, 0)
        self.assertEqual(quotes[0].limit_volume, 500000)
        self.assertEqual(quotes[0].term_months, 6)
        self.assertEqual(quotes[0].start_from, datetime(2015, 11, 01))
        self.assertEqual(quotes[0].start_until, datetime(2015, 12, 01))
        self.assertEqual(quotes[0].valid_until, datetime(2015, 11, 03))
        self.assertEqual(quotes[0].valid_from, datetime(2015, 11, 02))
        self.assertEqual(quotes[0].rate_class_alias, "Connecticut Light & Power-Residential-Residential")


        self.assertEqual(quotes[1].price, 0.1000)
        self.assertEqual(quotes[1].min_volume, 0)
        self.assertAlmostEqual(quotes[1].limit_volume, 500000, delta=2)
        self.assertEqual(quotes[1].term_months, 6)
        self.assertEqual(quotes[1].start_from, datetime(2015, 12, 01))
        self.assertEqual(quotes[1].start_until, datetime(2016, 01, 01))
        self.assertEqual(quotes[1].valid_until, datetime(2015, 11, 03))
        self.assertEqual(quotes[1].valid_from, datetime(2015, 11, 02))
        self.assertEqual(quotes[1].rate_class_alias, "Connecticut Light & Power-Residential-Residential")

        self.assertEqual(quotes[2].price, 0.0969)

        found_needle = False
        for quote in quotes:
            # We need to make sure all important fields are not null - we earlier caught a problem
            # in which valid_from was Null and the brokerage model did not catch it.
            fields = ['price', 'rate_class_alias', 'min_volume', 'limit_volume', 'term_months',
                      'valid_from', 'valid_until', 'start_from', 'start_until']
            for field in fields:
                self.assertIsNotNone(getattr(quote, field))

            # This is a random one I picked out from the 3rd sheet in the spreadsheet.
            if quote.price == 0.082 and quote.rate_class_alias == 'JCPL-Commercial-GSCL (>100KW Demand)' \
                and quote.start_from == datetime(2015, 12, 01):
                found_needle = True
                self.assertAlmostEqual(quote.min_volume, 100000, delta=2)
                self.assertAlmostEqual(quote.limit_volume, 500000, delta=2)
                self.assertEqual(quote.term_months, 12)

        # Assert that we found the above-mentioned quote.
        self.assertTrue(found_needle)

        # Last qouote from the spreadsheet.
        self.assertEqual(quotes[-1].price, 0.0711)
        self.assertAlmostEqual(quotes[-1].min_volume, 500000, delta=2)
        self.assertAlmostEqual(quotes[-1].limit_volume, 1000000, delta=2)
        self.assertEqual(quotes[-1].term_months, 24)
        self.assertEqual(quotes[-1].start_from, datetime(2016, 04, 01))
        self.assertEqual(quotes[-1].start_until, datetime(2016, 05, 01))
        self.assertEqual(quotes[-1].valid_until, datetime(2015, 11, 03))
        self.assertEqual(quotes[-1].valid_from, datetime(2015, 11, 02))
        self.assertEqual(quotes[-1].rate_class_alias,
                         "Penn Power-Commercial-Commerical: C1, C2, C3, CG, CH, GH1, GH2, GS1, GS3")

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
        self.assertEqual(8415, len(quotes))
        self.assertEqual(8415, parser.get_count())
        for quote in quotes:
            quote.validate()

        # since there are so many, only check one
        q1 = quotes[0]
        self.assertEqual(datetime(2015, 11, 1), q1.start_from)
        self.assertEqual(datetime(2015, 12, 1), q1.start_until)
        self.assertEqual(12, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2015, 11, 12), q1.valid_from)
        self.assertEqual(datetime(2015, 11, 13), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(100 * 1000, q1.limit_volume)
        self.assertEqual('IL-Ameren_Zone_1_CIPS-DS2-SECONDARY', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.05628472538457212, q1.price)

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
        self.assertEqual(datetime(2015, 12, 1), q1.start_from)
        self.assertEqual(datetime(2016, 1, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(12, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(100000, q1.limit_volume)
        self.assertEqual('PA-DQE-GS-General service', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.07063, q1.price)

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
            parser.load_file(spreadsheet,
                             file_name=basename(self.CONSTELLATION_FILE_PATH))
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(10451, len(quotes))

        for quote in quotes:
            quote.validate()

        q = quotes[0]
        self.assertEqual(datetime(2015, 10, 1), q.start_from)
        self.assertEqual(datetime(2015, 11, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(30 * 1000, q.limit_volume)
        self.assertEqual('CT-CLP', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.114373, q.price)

        q = quotes[-1]
        self.assertEqual(datetime(2016, 6, 1), q.start_from)
        self.assertEqual(datetime(2016, 7, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(36, q.term_months)
        self.assertEqual(500 * 1000, q.min_volume)
        self.assertEqual(1000 * 1000, q.limit_volume)
        self.assertEqual('NJ-AECO', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.090746, q.price)


    def test_major_energy(self):
        parser = MajorEnergyMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.MAJOR_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        # 3744 non-blank cells in electric sheet + 148 in gas sheet
        self.assertEqual(3892, len(quotes))

        for quote in quotes:
            quote.validate()

        # first quote is electric
        q = quotes[0]
        self.assertEqual(datetime(2015, 10, 27), q.valid_from)
        self.assertEqual(datetime(2015, 11, 3), q.valid_until)
        self.assertEqual(datetime(2015, 11, 1), q.start_from)
        self.assertEqual(datetime(2015, 12, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(74000, q.limit_volume)
        self.assertEqual('electric-IL-ComEd-', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.0652, q.price)

        # last quote is gas
        q = quotes[-1]
        self.assertEqual(datetime(2015, 10, 27), q.valid_from)
        self.assertEqual(datetime(2015, 11, 3), q.valid_until)
        self.assertEqual(datetime(2016, 2, 1), q.start_from)
        self.assertEqual(datetime(2016, 3, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(24, q.term_months)
        self.assertEqual(None, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual('gas-NY-RGE', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.3843, q.price)

    def test_sfe(self):
        parser = SFEMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.SFE_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet,
            file_name='SFE Pricing Worksheet - Sep 8 2015')
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(4356, len(quotes))

        for quote in quotes:
            quote.validate()

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(150000, q.limit_volume)
        self.assertEqual('NY-A (NiMo, NYSEG)', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.05911930642465754, q.price)

        # check volume ranges in many rows rows because SFE's units are
        # complicated
        q = quotes[5]
        self.assertEqual(150000, q.min_volume)
        self.assertEqual(500000, q.limit_volume)
        q = quotes[10]
        self.assertEqual(500000, q.min_volume)
        self.assertEqual(1e6, q.limit_volume)
        q = quotes[15]
        self.assertEqual(1e6, q.min_volume)
        self.assertEqual(2e6, q.limit_volume)
        q = quotes[20]
        self.assertEqual(2e6, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        q = quotes[25]
        self.assertEqual(0, q.min_volume)
        self.assertEqual(150000, q.limit_volume)

        q = quotes[4355]
        # TODO: date should probably be June 1, not June 30, right?
        self.assertEqual(datetime(2016, 6, 30), q.start_from)
        self.assertEqual(datetime(2016, 7, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(36, q.term_months)
        self.assertEqual(500000, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual('NJ-SJG ($/therm)', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.48745407444444444, q.price)

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

    def test_liberty(self):
        parser = LibertyMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.LIBERTY_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        # TODO: update to match this spreadsheet
        #self.assertEqual(1008, len(quotes))

        for quote in quotes:
            quote.validate()

        # First quote on first page from first table
        q1 = quotes[0]

        # Last quote from first page from last table (super saver)
        q2 = quotes[1007]

        # Last quote (super saver) from last table on last readable sheet
        q3 = quotes[-1]

        # TODO: update to match this spreadsheet
        self.assertEqual(datetime(2015, 9, 11), q1.valid_from)
        self.assertEqual(datetime(2015, 9, 12), q1.valid_until)
        self.assertEqual(datetime(2015, 10, 1), q1.start_from)
        self.assertEqual(datetime(2015, 11, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(3, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(25000, q1.limit_volume)
        self.assertEqual(0.10913, q1.price)
        self.assertEqual('PEPCO-DC-PEPCO-Default', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)

        self.assertEqual(21, q2.term_months)
        self.assertEqual(0.08087, q2.price)
        self.assertEqual(datetime(2015, 9, 11), q2.valid_from)
        self.assertEqual(datetime(2015, 9, 12), q2.valid_until)
        self.assertEqual(datetime(2016, 3, 1), q2.start_from)
        self.assertEqual(datetime(2016, 4, 1), q2.start_until)
        self.assertEqual('PEPCO-DC-PEPCO-GTLV/DMGT', q2.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q2.rate_class_id)
        self.assertEqual(500000, q2.min_volume)
        self.assertEqual(2000000, q2.limit_volume)

        self.assertEqual(15, q3.term_months)
        self.assertEqual(0.07868, q3.price)
        self.assertEqual(datetime(2015, 9, 11), q3.valid_from)
        self.assertEqual(datetime(2015, 9, 12), q3.valid_until)
        self.assertEqual(datetime(2016, 3, 1), q3.start_from)
        self.assertEqual(datetime(2016, 4, 1), q3.start_until)
        self.assertEqual('WPP-APS-SOHO (Tax ID Required)', q3.rate_class_alias)
        self.assertEqual(0, q3.min_volume)
        self.assertEqual(2000000, q3.limit_volume)

    def test_guttman(self):
        pass


