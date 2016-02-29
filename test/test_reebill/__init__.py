from core import init_model
from test import init_test_config
from test import create_tables
from test.setup_teardown import FakeS3Manager


def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    FakeS3Manager.start()

def tearDownModule():
    FakeS3Manager.stop()

__all__ = ['ExporterTest', 'FetchTest', 'JournalTest', 'ReebillTestWithDB',
           'StateDBTest']
