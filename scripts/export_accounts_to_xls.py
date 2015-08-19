from argparse import ArgumentParser
from datetime import datetime
from reebill import reebill_model
from reebill.payment_dao import PaymentDAO
from reebill.reebill_dao import ReeBillDAO
from reebill.reports.excel_export import Exporter

if __name__ == '__main__':
    parser = ArgumentParser(description="Command line tool\
    downloading OLTP data.")

    parser.add_argument("-f", "--filename", dest="filename",
                        help="xls filename.", required=True)
    args = parser.parse_args()

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

    with open(args.filename, 'wb') as output_file:
        exporter.export_reebill_details(output_file)
