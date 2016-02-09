from datetime import datetime
import re
from os.path import join, basename
from unittest import TestCase, skip
from mock import Mock

from nose.plugins.attrib import attr

from brokerage.brokerage_model import RateClass, RateClassAlias
from brokerage.quote_parser import QuoteParser, SpreadsheetReader
from brokerage.quote_parsers.guttman_electric import GuttmanElectric
from brokerage.quote_parsers.guttman_gas import GuttmanGas
from brokerage.quote_parsers import (
    DirectEnergyMatrixParser, USGEGasMatrixParser, AEPMatrixParser, EntrustMatrixParser,
    AmerigreenMatrixParser, ChampionMatrixParser, LibertyMatrixParser,
    ConstellationMatrixParser, MajorEnergyMatrixParser, SFEMatrixParser,
    USGEElectricMatrixParser, GEEMatrixParser, GEEGasPDFParser, VolunteerMatrixParser)
from core import ROOT_PATH, init_altitude_db, init_model
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
            reader = Mock()

            def __init__(self):
                super(ExampleQuoteParser, self).__init__()
                self.reader = reader

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
        self.assertEqual((10000, 20000), (low, high))
        self.reader.get_matches.assert_called_once_with(0, 0, 0, self.regex,
                                                        (int, int))


class MatrixQuoteParsersTest(TestCase):
    # paths to example spreadsheet files from each supplier
    DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage', 'quote_files')
    AEP_FILE_PATH = join(DIRECTORY,
                         'AEP Energy Matrix 3.0 2015-11-12.xls')
    DIRECT_ENERGY_FILE_PATH = join(DIRECTORY,
                                   'Matrix 1 Example - Direct Energy.xls')
    USGE_FILE_PATH = join(DIRECTORY, 'Matrix 2a Example - USGE.xlsx')
    USGE_ELECTRIC_FILE_PATH = join(DIRECTORY, 'USGE Matrix Pricing - ELEC - 20151102.xlsx')
    USGE_ELECTRIC_ANOMALY_PATH = join(DIRECTORY, 'USGEMatrixPricing-ELEC-20151130.xlsx')
    CHAMPION_FILE_PATH = join(
        DIRECTORY, 'Champion MM PJM Fixed-Index-24 Matrix 2015-10-30.xls')
    # using version of the file converted to XLS because we can't currently
    # read the newer format
    AMERIGREEN_FILE_PATH = join(DIRECTORY, 'Amerigreen Matrix 08-03-2015.xlsx')
    CONSTELLATION_FILE_PATH = join(
        DIRECTORY, 'Constellation - SMB Cost+ Matrix_Fully '
                   'Bundled_09_24_2015.xlsm')
    SFE_FILE_PATH = join(DIRECTORY, 'SFE Pricing Worksheet - Jan 15 2016.xlsx')
    MAJOR_FILE_PATH = join(
        DIRECTORY, 'Major Energy - Commercial and Residential Electric and '
                   'Gas Rack Rates October 27 2015.xlsx')
    ENTRUST_FILE_PATH = join(DIRECTORY, 'Matrix 10 Entrust.xlsx')
    LIBERTY_FILE_PATH = join(
        DIRECTORY, 'Liberty Power Daily Pricing for NEX ABC 2016-01-05.xlsx')
    GUTTMAN_DEO_FILE_PATH = join(DIRECTORY, 'Guttman', 'DEO_Matrix_02042016.xlsx')
    GUTTMAN_OH_DUKE_FILE_PATH = join(DIRECTORY, 'Guttman', 'OH_Duke_Gas_Matrix_02042016.xlsx')
    GUTTMAN_PEOPLE_TWP_FILE_PATH = join(DIRECTORY, 'Guttman', 'PeoplesTWP_Matrix_02042016.xlsx')
    GUTTMAN_CPA_MATRIX_FILE_PATH = join(DIRECTORY, 'Guttman', 'CPA_Matrix_02042016.xlsx')
    GUTTMAN_PEOPLE_MATRIX_FILE_PATH = join(DIRECTORY, 'Guttman', 'Peoples_Matrix_02042016.xlsx')
    GUTTMAN_COH_MATRIX_FILE_PATH = join(DIRECTORY, 'Guttman', 'COH_Matrix_02042016.xlsx')
    GUTTMAN_OH_POWER_FILE_PATH = join(DIRECTORY, 'Guttman', 'Guttman Energy OH Power Matrices 2.4.16.xlsx')
    GUTTMAN_PA_POWER_FILE_PATH = join(DIRECTORY, 'Guttman', 'Guttman Energy PA Power Matrices 2.4.16.xlsx')
    GEE_FILE_PATH_NY = join(DIRECTORY, 'GEE Rack Rate_NY_12.1.2015.xlsx')
    GEE_FILE_PATH_NJ = join(DIRECTORY, 'GEE Rack Rates_NJ_12.1.2015.xlsx')
    GEE_FILE_PATH_MA = join(DIRECTORY, 'GEE Rack Rates_MA_12.1.2015.xlsx')
    GEE_GAS_PATH_NJ = join(DIRECTORY, 'NJ Rack Rates_1.7.2016.pdf')
    VOLUNTEER_FILE_PATH_COH = join(DIRECTORY, 'volunteer',
                                   'Exchange_COH_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_CON = join(DIRECTORY, 'volunteer',
                                   'EXCHANGE_CON_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_DEO = join(DIRECTORY, 'volunteer',
                                   'Exchange_DEO_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_DTE = join(DIRECTORY, 'volunteer',
                                   'EXCHANGE_DTE_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_DUKE = join(DIRECTORY, 'volunteer',
                                    'Exchange_DUKE_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_PNG = join(DIRECTORY, 'volunteer',
                                   'Exchange_PNG_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_VEDO = join(DIRECTORY, 'volunteer',
                                    'Exchange_VEDO_2015 12-7-15.pdf')
    VOLUNTEER_FILE_PATH_PECO = join(DIRECTORY, 'volunteer',
                                    'PECO EXCHANGE_2015 12-7-15.pdf')

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
            # Direct Energy. Yes, it's SUPPOSED to look that way with the -- at the end.
            'Direct-electric-CT-CLP-37, R35--',
            # USGE
            'USGE-gas-Columbia of Kentucky-Residential-Residential',
            'USGE-electric-Columbia of Kentucky-Residential-Residential',
            # AEP
            'AEP-electric-DC-PEPCO_DC-GS-GSLV ND, GS LV, GS 3A',
            # Champion
            'Champion-electric-PA-DQE-GS-General service',
            # Amerigreen
            'Amerigreen-gas-NY-Con Ed',
            # Constellation
            'CT-CLP',
            'NJ-AECO',
            # liberty
            'Liberty-electric-PEPCO-DC-PEPCO-Default',
            'Liberty-electric-PEPCO-DC-PEPCO-GTLV/DMGT',
            # Major Energy
            'Major-electric-IL-ComEd-',
            'Major-gas-NY-RGE',
            # SFE
            'SFE-electric-NY-A (NiMo, NYSEG)',
            'SFE-gas-NJ-SJG ($/therm)',
            # Entrust
            'Entrust-electric-Com Ed',
            'Entrust-electric-ConEd Zone J',

            # Great Eastern Energy
            'GEE-electric-ConEd-J-SC-02',

            # Volunteer
            'Volunteer-gas-COLUMBIA GAS of OHIO (COH)'
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
        self.assertEqual('Direct-electric-CT-CLP-37, R35--', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(.07036, q1.price)

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
        self.assertEqual(quotes[0].rate_class_alias, "USGE-electric-Connecticut Light & Power-Residential-Residential-")

        self.assertEqual(quotes[1].price, 0.1000)
        self.assertEqual(quotes[1].min_volume, 0)
        self.assertAlmostEqual(quotes[1].limit_volume, 500000, delta=2)
        self.assertEqual(quotes[1].term_months, 6)
        self.assertEqual(quotes[1].start_from, datetime(2015, 12, 01))
        self.assertEqual(quotes[1].start_until, datetime(2016, 01, 01))
        self.assertEqual(quotes[1].valid_until, datetime(2015, 11, 03))
        self.assertEqual(quotes[1].valid_from, datetime(2015, 11, 02))
        self.assertEqual(quotes[1].rate_class_alias, "USGE-electric-Connecticut Light & Power-Residential-Residential-")

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
            if quote.price == 0.082 and quote.rate_class_alias == 'USGE-electric-JCPL-Commercial-GSCL (>100KW Demand)-' \
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
                         "USGE-electric-Penn Power-Commercial-Commerical: C1, C2, C3, CG, CH, GH1, GH2, GS1, GS3-PJMATSI")


    def test_usge(self):
        parser = USGEGasMatrixParser()
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
        self.assertEqual('USGE-gas-Columbia of Kentucky-Residential-Residential', q1.rate_class_alias)
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
        self.assertEqual('USGE-gas-Baltimore Gas & Electric-Residential-Residential', q1.rate_class_alias)
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
        # self.assertEqual('Residential', q1.rate_class_alias)
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

    def test_guttman_electric(self):
        parser = GuttmanElectric()
        self.assertEqual(0, parser.get_count())
        with open(self.GUTTMAN_OH_POWER_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(1440, len(quotes))
        self.assertEqual(1440, parser.get_count())

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 04, 01), q1.start_from)
        self.assertEqual(datetime(2016, 05, 01), q1.start_until)
        self.assertEqual(12, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 02, 04, 8, 42, 49), q1.valid_from)
        self.assertEqual(datetime(2016, 02, 05, 8, 42, 49), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(250000, q1.limit_volume)
        self.assertEqual('Guttman-electric-Ohio_AEP_OH_CS_GS-1', q1.rate_class_alias)
        # self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.0523100684762365, q1.price)

        q2 = quotes[1439]
        self.assertEqual(datetime(2017, 03, 01), q2.start_from)
        self.assertEqual(datetime(2017, 04, 01), q2.start_until)
        self.assertEqual(36, q2.term_months)
        self.assertEqual(datetime.utcnow().date(), q2.date_received.date())
        self.assertEqual(datetime(2016, 02, 04, 8, 51, 30), q2.valid_from)
        self.assertEqual(datetime(2016, 02, 05, 8, 51, 30), q2.valid_until)
        self.assertEqual(250001, q2.min_volume)
        self.assertEqual(500000, q2.limit_volume)
        self.assertEqual('Guttman-electric-Ohio_Toledo Edison_GS', q2.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q2.purchase_of_receivables)
        self.assertEqual(0.0565063914882725, q2.price)

        parser = GuttmanElectric()
        self.assertEqual(0, parser.get_count())
        with open(self.GUTTMAN_PA_POWER_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(1920, len(quotes))
        self.assertEqual(1920, parser.get_count())

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 04, 01), q1.start_from)
        self.assertEqual(datetime(2016, 05, 01), q1.start_until)
        self.assertEqual(12, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 51, 40), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 51, 40), q1.valid_until)
        self.assertEqual(125000, q1.min_volume)
        self.assertEqual(250000, q1.limit_volume)
        self.assertEqual('Guttman-electric-Pennsylvania_Duquesne_DQE_GS', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.0665074230983375, q1.price)

        q2 = quotes[1919]
        self.assertEqual(datetime(2017, 03, 01), q2.start_from)
        self.assertEqual(datetime(2017, 04, 01), q2.start_until)
        self.assertEqual(36, q2.term_months)
        self.assertEqual(datetime.utcnow().date(), q2.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 52, 20), q2.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 52, 20), q2.valid_until)
        self.assertEqual(250001, q2.min_volume)
        self.assertEqual(500000, q2.limit_volume)
        self.assertEqual('Guttman-electric-Pennsylvania_West Penn Power_30', q2.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q2.purchase_of_receivables)
        self.assertEqual(0.0625273435516683, q2.price)

    def test_guttman_gas(self):
        parser = GuttmanGas()
        self.assertEqual(0, parser.get_count())
        with open(self.GUTTMAN_DEO_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        self.assertEqual(340, len(quotes))
        self.assertEqual(340, parser.get_count())

        for quote in quotes:
            quote.validate()

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 43, 24), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 43, 24), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Ohio_Dominion_OH_NG', q1.rate_class_alias)
        # self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.288514151909343, q1.price)

        parser = GuttmanGas()
        with open(self.GUTTMAN_OH_DUKE_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())
        quotes = list(parser.extract_quotes())
        self.assertEqual(170, len(quotes))
        self.assertEqual(170, parser.get_count())

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 43, 39), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 43, 39), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Ohio_Duke_OH_NG', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.382672151434036, q1.price)

        parser = GuttmanGas()
        with open(self.GUTTMAN_PEOPLE_TWP_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())
        quotes = list(parser.extract_quotes())
        self.assertEqual(170, len(quotes))
        self.assertEqual(170, parser.get_count())

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 52, 10), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 52, 10), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Pennsylvania_PNG_PA-TWP', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.25010806097029203, q1.price)

        parser = GuttmanGas()
        with open(self.GUTTMAN_CPA_MATRIX_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())
        quotes = list(parser.extract_quotes())
        self.assertEqual(340, len(quotes))
        self.assertEqual(340, parser.get_count())

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 51, 34), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 51, 34), q1.valid_until)
        self.assertEqual(3001, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Pennsylvania_ColumbiaGas_PA', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.335108676605036, q1.price)

        parser = GuttmanGas()
        with open(self.GUTTMAN_PEOPLE_MATRIX_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())
        quotes = list(parser.extract_quotes())
        self.assertEqual(170, len(quotes))
        self.assertEqual(170, parser.get_count())

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 52, 4), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 52, 4), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Pennsylvania_PNG_PA', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.249393339931405, q1.price)

        parser = GuttmanGas()
        with open(self.GUTTMAN_COH_MATRIX_FILE_PATH, 'rb') as \
                spreadsheet:
            parser.load_file(spreadsheet)
        parser.validate()
        self.assertEqual(0, parser.get_count())
        quotes = list(parser.extract_quotes())
        self.assertEqual(510, len(quotes))
        self.assertEqual(510, parser.get_count())

        q1 = quotes[0]
        self.assertEqual(datetime(2016, 03, 16), q1.start_from)
        self.assertEqual(datetime(2016, 04, 01), q1.start_until)
        self.assertEqual(6, q1.term_months)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(datetime(2016, 2, 4, 8, 43, 9), q1.valid_from)
        self.assertEqual(datetime(2016, 2, 5, 8, 43, 9), q1.valid_until)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(5 * 1000, q1.limit_volume)
        self.assertEqual('Guttman-gas-Ohio_ColumbiaGas_OH', q1.rate_class_alias)
        #self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.421905135494187, q1.price)

    def test_aep(self):
        parser = AEPMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.AEP_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet,
                             file_name=basename(self.AEP_FILE_PATH))
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
        self.assertEqual('AEP-electric-IL-Ameren_Zone_1_CIPS-DS2-SECONDARY', q1.rate_class_alias)
        # self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.05628, q1.price)

    def test_champion(self):
        parser = ChampionMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.CHAMPION_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet, file_name=basename(
                self.CHAMPION_FILE_PATH))
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
        self.assertEqual('Champion-electric-PA-DQE-GS-General service', q1.rate_class_alias)
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
        self.assertEqual('Amerigreen-gas-NY-Con Ed', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)
        self.assertEqual(0.3403, q1.price)

    def test_constellation(self):
        # Constellation is NO LONGER SUPPORTED.
        pass

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

    def test_gee_gas(self):
        parser = GEEGasPDFParser()

        with open(self.GEE_GAS_PATH_NJ, 'rb') as pdf_file:
            parser.load_file(pdf_file)
            parser.validate()
            quotes_nj = list(parser.extract_quotes())

        self.assertEqual(len(quotes_nj), 128)

        self.assertAlmostEqual(quotes_nj[0].price, 0.3591, delta=0.000001)
        self.assertEqual(quotes_nj[0].min_volume, 0)
        self.assertEqual(quotes_nj[0].limit_volume, 9999)
        self.assertEqual(quotes_nj[0].term_months, 6)
        self.assertEqual(quotes_nj[0].start_from, datetime(2016, 1, 1))
        self.assertEqual(quotes_nj[0].valid_from, datetime(2016, 1, 7))
        self.assertEqual(quotes_nj[0].valid_until, datetime(2016, 1, 8))
        self.assertEqual(quotes_nj[0].rate_class_alias, 'GEE-gas-NJ Commercial-Etown-Non-Heat')
        self.assertIn('NJ Commercial,Etown Non-Heat,start 2016-01-01,6 month,0.3591', quotes_nj[0].file_reference[0])

        self.assertEqual(quotes_nj[-22].min_volume, 0)
        self.assertEqual(quotes_nj[-22].limit_volume, 9999)
        self.assertEqual(quotes_nj[-22].term_months, 18)
        self.assertEqual(quotes_nj[-22].start_from, datetime(2016, 3, 1))
        self.assertEqual(quotes_nj[-22].start_until, datetime(2016, 4, 1))
        self.assertEqual(quotes_nj[-22].valid_from, datetime(2016, 1, 7))
        self.assertAlmostEqual(quotes_nj[-22].price, 0.5372, delta=0.000001)

        self.assertAlmostEqual(quotes_nj[-1].price, 0.5057, delta=0.000001)
        self.assertEqual(quotes_nj[-1].min_volume, 0)
        self.assertEqual(quotes_nj[-1].limit_volume, 9999)
        self.assertEqual(quotes_nj[-1].term_months, 24)
        self.assertEqual(quotes_nj[-1].start_from, datetime(2016, 4, 1))
        self.assertEqual(quotes_nj[-1].start_until, datetime(2016, 5, 1))
        self.assertEqual(quotes_nj[-1].valid_from, datetime(2016, 1, 7))

    def test_gee_electric(self):
        parser = GEEMatrixParser()

        with open(self.GEE_FILE_PATH_MA, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
            parser.validate()
            quotes_ma = list(parser.extract_quotes())

        with open(self.GEE_FILE_PATH_NJ, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
            parser.validate()
            quotes_nj = list(parser.extract_quotes())

        with open(self.GEE_FILE_PATH_NY, 'rb') as spreadsheet:
            parser.load_file(spreadsheet)
            parser.validate()
            quotes_ny = list(parser.extract_quotes())

        self.assertGreaterEqual(len(quotes_ma) + len(quotes_nj) + len(quotes_ny), 1000)
        q = quotes_ny[0]
        self.assertEqual(datetime(2015, 12, 1), q.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q.valid_until)
        self.assertEqual(datetime(2015, 12, 1), q.start_from)
        self.assertEqual(datetime(2016, 1, 1), q.start_until)
        self.assertEqual('GEE-electric-ConEd-J-SC-02', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(499999, q.limit_volume)
        self.assertEqual(0.08381, q.price)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual('electric', q.service_type)

        ql = quotes_ny[-1]
        self.assertEqual(datetime(2015, 12, 1), ql.valid_from)
        self.assertEqual(datetime(2015, 12, 2), ql.valid_until)
        self.assertEqual(datetime(2016, 5, 1), ql.start_from)
        self.assertEqual(datetime(2016, 6, 1), ql.start_until)
        self.assertEqual(24, ql.term_months)
        self.assertEqual(500000, ql.min_volume)
        self.assertEqual(999999, ql.limit_volume)
        self.assertAlmostEqual(0.07573, ql.price, delta=0.000001)

        q_nj_0 = quotes_nj[0]
        self.assertEqual(datetime(2015, 12, 1), q_nj_0.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q_nj_0.valid_until)
        self.assertEqual(datetime(2015, 12, 1), q_nj_0.start_from)
        self.assertEqual(datetime(2016, 1, 1), q_nj_0.start_until)
        self.assertEqual(6, q_nj_0.term_months)
        self.assertAlmostEqual(0.09789, q_nj_0.price, delta=0.000001)

        q_nj_l = quotes_nj[-1]
        self.assertEqual(datetime(2016, 5, 1), q_nj_l.start_from)
        self.assertEqual(datetime(2016, 6, 1), q_nj_l.start_until)
        self.assertEqual(24, q_nj_l.term_months)
        self.assertAlmostEqual(0.08219, q_nj_l.price, delta=0.000001)

        q_ma_0 = quotes_ma[0]
        self.assertEqual(datetime(2015, 12, 1), q_ma_0.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q_ma_0.valid_until)
        self.assertEqual(datetime(2015, 12, 1), q_ma_0.start_from)
        self.assertEqual(datetime(2016, 1, 1), q_ma_0.start_until)
        self.assertEqual(6, q_ma_0.term_months)
        self.assertAlmostEqual(0.09168, q_ma_0.price, delta=0.000001)

        q_ma_l = quotes_ma[-2]
        self.assertEqual(datetime(2015, 12, 1), q_ma_l.valid_from)
        self.assertEqual(datetime(2015, 12, 2), q_ma_l.valid_until)
        self.assertEqual(datetime(2016, 5, 1), q_ma_l.start_from)
        self.assertEqual(datetime(2016, 6, 1), q_ma_l.start_until)
        self.assertEqual(24, q_ma_l.term_months)
        self.assertEqual(500000, ql.min_volume)
        self.assertEqual(999999, ql.limit_volume)
        self.assertAlmostEqual(0.08888, q_ma_l.price, delta=0.000001)

        q_ma_l = quotes_ma[-1]
        self.assertEqual(datetime(2016, 5, 1), q_ma_l.start_from)
        self.assertEqual(datetime(2016, 6, 1), q_ma_l.start_until)
        self.assertEqual(6, q_ma_l.term_months)
        self.assertAlmostEqual(0.07356, q_ma_l.price, delta=0.000001)

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
        self.assertEqual('Major-electric-IL-ComEd-', q.rate_class_alias)
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
        self.assertEqual('Major-gas-NY-RGE', q.rate_class_alias)
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
        self.assertEqual(datetime(2016, 2, 1), q.start_from)
        self.assertEqual(datetime(2016, 3, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(6, q.term_months)
        self.assertEqual(0, q.min_volume)
        self.assertEqual(150000, q.limit_volume)
        self.assertEqual('SFE-electric-NY-A (NiMo, NYSEG)', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.0575, q.price)

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
        self.assertEqual(datetime(2016, 7, 31), q.start_from)
        self.assertEqual(datetime(2016, 8, 1), q.start_until)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(36, q.term_months)
        self.assertEqual(500000, q.min_volume)
        self.assertEqual(None, q.limit_volume)
        self.assertEqual('SFE-gas-NJ-SJG ($/therm)', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.4625, q.price)

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
        self.assertEqual('Entrust-electric-Com Ed', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.0812, q.price)

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
        self.assertEqual('Entrust-electric-ConEd Zone J', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(0.0811, q.price)

    def test_liberty(self):
        parser = LibertyMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.LIBERTY_FILE_PATH, 'rb') as spreadsheet:
            parser.load_file(spreadsheet, file_name=basename(
                self.LIBERTY_FILE_PATH))
        parser.validate()
        self.assertEqual(0, parser.get_count())

        quotes = list(parser.extract_quotes())
        # TODO: update to match this spreadsheet
        # self.assertEqual(1008, len(quotes))

        for quote in quotes:
            quote.validate()

        # First quote on first page from first table
        q1 = quotes[0]

        # Last quote from first page from last table (super saver)
        # (to get this index, break after the first iteration of the loop
        # through sheets)
        q2 = quotes[2159]

        # Last quote (super saver) from last table on last readable sheet
        q3 = quotes[-1]

        # validity dates are only checked once
        self.assertEqual(datetime(2016, 1, 5), q1.valid_from)
        self.assertEqual(datetime(2016, 1, 6), q1.valid_until)
        self.assertEqual(datetime(2016, 2, 1), q1.start_from)
        self.assertEqual(datetime(2016, 3, 1), q1.start_until)
        self.assertEqual(datetime.utcnow().date(), q1.date_received.date())
        self.assertEqual(3, q1.term_months)
        self.assertEqual(0, q1.min_volume)
        self.assertEqual(25000, q1.limit_volume)
        self.assertEqual(0.10178, q1.price)
        self.assertEqual('Liberty-electric-PEPCO-DC-PEPCO-Default', q1.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q1.rate_class_id)
        self.assertEqual(False, q1.purchase_of_receivables)

        self.assertEqual(30, q2.term_months)
        self.assertEqual(0.07959, q2.price)
        self.assertEqual(datetime(2017, 1, 1), q2.start_from)
        self.assertEqual(datetime(2017, 2, 1), q2.start_until)
        self.assertEqual('Liberty-electric-PEPCO-DC-PEPCO-GTLV/DMGT', q2.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q2.rate_class_id)
        self.assertEqual(500000, q2.min_volume)
        self.assertEqual(2000000, q2.limit_volume)

        self.assertEqual(15, q3.term_months)
        self.assertEqual(.07636, q3.price)
        self.assertEqual(datetime(2016, 7, 1), q3.start_from)
        self.assertEqual(datetime(2016, 8, 1), q3.start_until)
        self.assertEqual('Liberty-electric-WPP-APS-SOHO (Tax ID Required)', q3.rate_class_alias)
        self.assertEqual(0, q3.min_volume)
        self.assertEqual(2000000, q3.limit_volume)

    # TODO: this should be broken into separate test methods
    def test_volunteer(self):
        parser = VolunteerMatrixParser()
        self.assertEqual(0, parser.get_count())

        with open(self.VOLUNTEER_FILE_PATH_COH) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-COLUMBIA GAS of OHIO (COH)', q.rate_class_alias)
        self.assertEqual(self.rate_class.rate_class_id, q.rate_class_id)
        self.assertEqual(False, q.purchase_of_receivables)
        self.assertEqual(4.39, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(3.99, q.price)

        with open(self.VOLUNTEER_FILE_PATH_CON) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-CONSUMERS ENERGY', q.rate_class_alias)
        self.assertEqual(3.65, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(3.65, q.price)

        with open(self.VOLUNTEER_FILE_PATH_DEO) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-DOMINION EAST OHIO (DEO)', q.rate_class_alias)
        self.assertEqual(3.55, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(3.39, q.price)

        with open(self.VOLUNTEER_FILE_PATH_DTE) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-DTE ENERGY', q.rate_class_alias)
        self.assertEqual(4.15, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(3.80, q.price)

        with open(self.VOLUNTEER_FILE_PATH_DUKE) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-DUKE ENERGY OHIO', q.rate_class_alias)
        self.assertEqual(4.35, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(4.0, q.price)

        with open(self.VOLUNTEER_FILE_PATH_PNG) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-PEOPLES NATURAL GAS (PNG)', q.rate_class_alias)
        self.assertEqual(3.95, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(3.95, q.price)

        with open(self.VOLUNTEER_FILE_PATH_VEDO) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-VECTREN ENERGY DELIVERY OHIO (VEDO)',
                         q.rate_class_alias)
        self.assertEqual(4.69, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(4.24, q.price)

        with open(self.VOLUNTEER_FILE_PATH_PECO) as quote_file:
            parser.load_file(quote_file)
        parser.validate()
        quotes = list(parser.extract_quotes())

        self.assertEqual(9, parser.get_count())
        self.assertEqual(9, len(quotes))

        q = quotes[0]
        self.assertEqual(datetime(2016, 1, 1), q.start_from)
        self.assertEqual(datetime(2016, 2, 1), q.start_until)
        self.assertEqual(12, q.term_months)
        self.assertEqual(datetime.utcnow().date(), q.date_received.date())
        self.assertEqual(datetime(2015, 12, 7), q.valid_from)
        self.assertEqual(datetime(2015, 12, 12), q.valid_until)
        self.assertEqual(2500, q.min_volume)
        self.assertEqual(6e4, q.limit_volume)
        self.assertEqual('Volunteer-gas-PECO ENERGY COMPANY (PECO)', q.rate_class_alias)
        self.assertEqual(4.6, q.price)

        # last quote: only check things that are different from above
        q = quotes[-1]
        self.assertEqual(24, q.term_months)
        self.assertEqual(4.6, q.price)
