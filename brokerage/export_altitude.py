from uuid import uuid4
from datetime import timedelta
from tablib import Dataset
from core.model import Session, UtilBill, UtilityAccount
from util.dateutils import ISO_8601_DATETIME
from brokerage.brokerage_model import BrokerageAccount

def _load_pg_utilbills():
    '''Return an iterator of all UtilBills that have a BrokerageAccount.
    '''
    return Session().query(UtilBill).join(UtilityAccount).join(
        BrokerageAccount)

class PGAltitudeExporter(object):

    def __init__(self, uuid_func, altitude_converter):
        '''
        :param uuid_func:  a callable that returns UUID objects or strings,
        such as any of the functions in the 'uuid' module.
        :param  altitude_converter: matches interface of core.altitude
        (get_guid_for_utility and get_guid_for_supplier methods), used for
        unit testing.
        '''
        self._uuid_func = uuid_func
        self._altitude_converter = altitude_converter

    def write_csv(self, utilbills, file):
        '''Write CSV of data to 'file'.
        :param utilbills: iterator of UtilBills to include data from.
        :param file: destination file.
        '''
        dataset = self.get_dataset(utilbills)
        file.write(dataset.csv)

    def get_dataset(self, utilbills):
        '''Return a tablib.Dataset containing the data that is supposed to be
        exported.
        :param utilbills: iterator of UtilBills to include data from.
        '''
        dataset = Dataset(headers=[
            'billing_customer_id',
            'utility_bill_guid',
            'utility_guid',
            'supplier_guid',
            'service_type',
            'utility_account_number',
            'billing_period_start_date',
            'billing_period_end_date',
            'total_usage',
            'total_supply_charge',
            'rate_class',
            'secondary_account_number',
            'service_address_street',
            'service_address_city',
            'service_address_state',
            'service_address_postal_code',
            'create_date',
            'modified_date',
        ])
        def format_date(d):
            if d is None:
                return ''
            return d.strftime(ISO_8601_DATETIME)
        def format_possible_none(g):
            if g is None:
                return ''
            return g
        for ub in utilbills:
            append_row_as_dict(dataset, {
                'billing_customer_id': ub.get_nextility_account_number(),
                'utility_bill_guid':
                    self._altitude_converter.get_or_create_guid_for_utilbill(
                        ub, self._uuid_func),
                'utility_guid':
                    format_possible_none(self._altitude_converter.get_guid_for_utility(
                        ub.get_utility())),
                'supplier_guid':
                    format_possible_none(self._altitude_converter.get_guid_for_supplier(
                        ub.get_supplier())),
                'service_type': ub.get_service(),
                'utility_account_number': ub.get_utility_account_number(),
                'billing_period_start_date':  format_date(ub.period_start),
                'billing_period_end_date': format_date(ub.period_end),
                'total_usage': ub.get_total_energy_consumption(),
                'total_supply_charge': ub.get_supply_target_total(),
                'rate_class': format_possible_none(ub.get_rate_class_name()),
                'secondary_account_number': format_possible_none(
                    ub.supply_choice_id),
                'service_address_street': ub.service_address.street,
                'service_address_city': ub.service_address.city,
                'service_address_state': ub.service_address.state,
                'service_address_postal_code': ub.service_address.postal_code,
                'create_date': format_date(ub.date_received),
                'modified_date': format_date(ub.date_modified),
            })
        return dataset

# TODO maybe this is built into tablib already or should be added there.
def append_row_as_dict(dataset, row_dict):
    '''Append the values of 'row_dict' to 'dataset', using the keys to
    determine which column each value goes in.
    '''
    assert len(row_dict) == dataset.width
    row = [None] * dataset.width
    for i in xrange(dataset.width):
        row[i] = row_dict[dataset.headers[i]]
    dataset.append(row)

