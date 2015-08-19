from datetime import datetime
from reebill import reebill_model
from reebill.payment_dao import PaymentDAO
from reebill.reebill_dao import ReeBillDAO
from reebill.reports.excel_export import Exporter

if __name__ == '__main__':
    from os.path import dirname, realpath, join
    from core import init_config, init_model, init_logging

    p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
    init_logging()
    init_config()
    init_model()
    import logging

    logger = logging.getLogger('reebill')
    state_db = ReeBillDAO()
    payment_dao = PaymentDAO()
    exporter = Exporter(state_db, payment_dao)
    filename = "billing_all_accounts_export.xls"

    with open(filename, 'wb') as output_file:
        exporter.export_reebill_details(output_file)
