from datetime import datetime
from os.path import join
from unittest import TestCase

from brokerage.brokerage_model import RateClass, RateClassAlias
from core import ROOT_PATH, init_altitude_db, init_model
from brokerage.quote_parsers import DirectEnergyMatrixParser, USGEMatrixParser, \
    AEPMatrixParser, AmerigreenMatrixParser, ChampionMatrixParser, \
    ConstellationMatrixParser
from core.model import AltitudeSession
from test import create_tables, init_test_config, clear_db


def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    init_altitude_db()

class MatrixQuoteParsersTest(TestCase):
    # paths to example spreadsheet files from each supplier
    DIRECTORY = join(ROOT_PATH, 'test', 'test_brokerage')
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

