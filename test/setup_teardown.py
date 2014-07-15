

from os.path import realpath, join, dirname
import unittest
from StringIO import StringIO
import ConfigParser
import pymongo
from bson import ObjectId
import mongoengine
import MySQLdb
from datetime import date, datetime, timedelta
from sqlalchemy.exc import UnboundExecutionError
from billing import init_config, init_model
from billing.processing import mongo
from billing.processing import rate_structure2
from billing.processing.process import Process
from billing.processing.state import StateDB, Customer, Session
from billing.processing.billupload import BillUpload
from billing.processing.bill_mailer import Mailer
from billing.processing.render import ReebillRenderer
from billing.processing.fetch_bill_data import RenewableEnergyGetter
from billing.test import example_data
from nexusapi.nexus_util import MockNexusUtil
from skyliner.mock_skyliner import MockSplinter, MockSkyInstall
import logging



class TestCaseWithSetup(unittest.TestCase):
    '''Contains setUp/tearDown code for all test cases that need to use ReeBill
    databases.'''

    @staticmethod
    def init_logging():
        """Setup NullHandlers for test and root loggers.
        """
        testlogger = logging.getLogger('test')
        testlogger.addHandler(logging.NullHandler())
        testlogger.propagate = False

        rootlogger = logging.getLogger('root')
        rootlogger.addHandler(logging.NullHandler())
        rootlogger.propagate = False

    @staticmethod
    def insert_data():
        session = Session()
        session.execute("delete from charge")
        session.execute("delete from payment")
        session.execute("delete from reebill")
        session.execute("delete from utilbill")
        session.execute("delete from customer")
        session.add(Customer('Test Customer', '99999', .12, .34,
                            '000000000000000000000001', 'example@example.com'))
        session.commit()

        # insert template utilbill document for the customer in Mongo
        db = pymongo.Connection('localhost')['test']
        utilbill = example_data.get_utilbill_dict('99999',
                start=date(1900,01,01), end=date(1900,02,01),
                utility='washgas', service='gas')
        utilbill['_id'] = ObjectId('000000000000000000000001')
        db.utilbills.save(utilbill)

    def init_dependencies(self):
        """Configure connectivity to various other systems and databases.
        """
        from billing import config

        logger = logging.getLogger('test')

        self.state_db = StateDB(Session, logger)
        self.billupload = BillUpload(config, logger)

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])

        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                pymongo.Connection('localhost', 27017)['test'])

        self.rate_structure_dao = rate_structure2.RateStructureDAO(
                logger=logger)

        # TODO: 64956642 do not hard code nexus names
        self.nexus_util = MockNexusUtil([
            {
                'billing': '99999',
                'olap': 'example-1',
                'casualname': 'Example 1',
                'primus': '1785 Massachusetts Ave.',
            },
            {
                'billing': '88888',
                'olap': 'example-2',
                'casualname': 'Example 2',
                'primus': '1786 Massachusetts Ave.',
            },
        ])

        bill_mailer = Mailer({
            # TODO 64956668
        })

        renderer = ReebillRenderer({
            'temp_directory': '/tmp',
            'template_directory': join(dirname(realpath(__file__)), '..',
                    'reebill_templates'),
            'default_template': '/dev/null',
            'teva_accounts': '',
        }, self.state_db, self.reebill_dao,
                logger)

        ree_getter = RenewableEnergyGetter(self.splinter, self.reebill_dao, logger)

        self.process = Process(self.state_db, self.reebill_dao,
                self.rate_structure_dao, self.billupload, self.nexus_util,
                bill_mailer, renderer, ree_getter,
                self.splinter, logger=logger)

        mongoengine.connect('test', host='localhost', port=27017,
                            alias='utilbills')
        mongoengine.connect('test', host='localhost', port=27017,
                            alias='ratestructure')

    def setUp(self):
        """Sets up "test" databases in Mongo and MySQL, and crates DAOs:
        ReebillDAO, RateStructureDAO, StateDB, Splinter, Process,
        NexusUtil."""
        TestCaseWithSetup.init_logging()
        init_config('tstsettings.cfg')
        init_model()
        self.maxDiff = None # show detailed dict equality assertion diffs
        self.init_dependencies()
        TestCaseWithSetup.insert_data()

    def tearDown(self):
        '''Clears out databases.'''
        # clear out mongo test database
        mongo_connection = pymongo.Connection('localhost', 27017)
        mongo_connection.drop_database('test')

        # this helps avoid a "lock wait timeout exceeded" error when a test
        # fails to commit the SQLAlchemy session
        self.state_db.session.commit()
        Session.remove()


if __name__ == '__main__':
    unittest.main()
