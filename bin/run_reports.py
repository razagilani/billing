"""
There are various reports that run daily and a produce a file of cached data.
They can all be run from here.
"""
from core import initialize
from nexusapi.nexus_util import NexusUtil
from reebill.fetch_bill_data import RenewableEnergyGetter
from reebill.reebill_dao import ReeBillDAO
from reebill.reports.reconciliation import ReconciliationReport
from skyliner.mock_skyliner import MockSplinter
from skyliner.splinter import Splinter

def make_splinter():
    if config.get('reebill', 'mock_skyliner'):
        return MockSplinter()
    return Splinter(
        config.get('reebill', 'oltp_url'),
        skykit_host=config.get('reebill', 'olap_host'),
        skykit_db=config.get('reebill', 'olap_database'),
        olap_cache_host=config.get('reebill', 'olap_host'),
        olap_cache_db=config.get('reebill', 'olap_database'),
        monguru_options={
            'olap_cache_host': config.get('reebill', 'olap_host'),
            'olap_cache_db': config.get('reebill',
                                        'olap_database'),
            'cartographer_options': {
                'olap_cache_host': config.get('reebill',
                                              'olap_host'),
                'olap_cache_db': config.get('reebill',
                                            'olap_database'),
                'measure_collection': 'skymap',
                'install_collection': 'skyit_installs',
                'nexus_host': config.get('reebill',
                                         'nexus_db_host'),
                'nexus_db': 'nexus',
                'nexus_collection': 'skyline',
                },
            },
        cartographer_options={
            'olap_cache_host': config.get('reebill', 'olap_host'),
            'olap_cache_db': config.get('reebill',
                                        'olap_database'),
            'measure_collection': 'skymap',
            'install_collection': 'skyit_installs',
            'nexus_host': config.get('reebill', 'nexus_db_host'),
            'nexus_db': 'nexus',
            'nexus_collection': 'skyline',
            },
    )

if __name__ == '__main__':
    initialize()
    from core import config
    reebill_dao = ReeBillDAO()
    splinter = make_splinter()
    nexus_util = NexusUtil(config.get('reebill', 'nexus_db_host'))
    ree_getter = RenewableEnergyGetter(splinter, nexus_util, None)

    reconciliation_report = ReconciliationReport(reebill_dao, ree_getter)
    reconciliation_path = config.get('reebill', 'reconciliation_report_path')
    with open(reconciliation_path, 'w') as output_file:
        reconciliation_report.write_json(output_file)
