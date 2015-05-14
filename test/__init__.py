def init_test_config():
    from core import init_config
    from os.path import realpath, join, dirname
    init_config(filepath=join(dirname(realpath(__file__)), 'tstsettings.cfg'))

__all__ = ['BillMailerTest', 'ReebillFileHandlerTest', 'ProcessTest',
           'ReebillProcessingTest', 'BillUploadTest', 'ChargeUnitTests',
           'RateStructureDAOTest', 'UtilBillTest', 'UtilbillLoaderTest',
           'UtilbillProcessingTest', 'ExporterTest', 'FetchTest',
           'JournalTest', 'ReebillTest', 'StateDBTest', 'DateUtilsTest',
           'HolidaysTest', 'MonthmathTest']

