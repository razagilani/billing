#!/usr/bin/python
'''Reports that involve computing approximate utility bill energy quantities or
charges over arbitarary periods of time.'''
import traceback
import argparse
from datetime import date, timedelta
from calendar import Calendar
from decimal import Decimal
from billing.processing import mongo
from billing.util import dateutils
import xlwt
import sys

calendar = Calendar()

def daily_average_energy(reebill_dao, account, day, service='gas',
        unit='therms'):
    # find out what reebill covers this day and has a utility bill of the right
    # service that covers day
    possible_reebills = reebill_dao.load_reebills_in_period(account,
            start_date=day, end_date=day)
    reebill = None

    # If none of the possible reebills have the desired service, then return
    # N/A because there are no applicable data. This isn't necessarily a failure state
    # deserving an Exception.
    if not any((service in rb.services for rb in possible_reebills)):
        return 'N/A'
    
    for possible_reebill in possible_reebills:
        if service in possible_reebill.services \
                and day >= possible_reebill.utilbill_period_for_service(service)[0] \
                and day < possible_reebill.utilbill_period_for_service(service)[1]:
            reebill = possible_reebill
            break
    if reebill is None:
        raise Exception("No reebills found for %s, %s" % (account, day))

    # get all non-shadow "REG_TOTAL" registers in all meters for this service,
    # and make sure there's at least one
    meters = reebill.meters_for_service(service)
    total_registers = [r for r in sum((meter['registers'] for meter in meters),
            []) if not r['shadow'] and r.get('register_binding', None) == 'REG_TOTAL']
    if total_registers == []:
        raise Exception('No REG_TOTAL registers in any meter for %s' % account)

    total_therms = 0
    for register in total_registers:
        quantity = register['quantity']
        quantity_unit = register['quantity_units'].lower()
        if quantity_unit == 'therms':
            total_therms += quantity
        elif quantity_unit == 'btu':
            total_therms += quantity / Decimal(100000.0)
        elif quantity_unit == 'kwh':
            total_therms += quantity / Decimal(.0341214163)
        elif quantity_unit == 'ccf':
            # TODO: 28825375 - need the conversion factor for this
            print ("Register in reebill %s-%s-%s contains gas measured "
                "in ccf: energy value is wrong; time to implement "
                "https://www.pivotaltracker.com/story/show/28825375") % (
                account, reebill.sequence, self.version)
            # assume conversion factor is 1
            total_therms += quantity
        else:
            raise ValueError('Unknown energy unit: "%s"' % \
                    register['quantity_units'])

    # convert therms into the caller's preferred energy unit
    if unit == 'therms':
        total_energy = total_therms
    elif unit == 'btu':
        total_energy = total_therms * Decimal(100000.0)
    elif unit == 'kwh':
        total_energy = total_therms * Decimal(.0341214163)
    else:
        raise Exception('Unknown energy unit: "%s"' % unit)

    # average total energy over number of days in utility bill period
    start_date, end_date = reebill.utilbill_period_for_service(service)
    days_in_period = (end_date - start_date).days
    return float(total_energy) / float(days_in_period)

def average_energy_for_date_range(reebill_dao, account, start_date, end_date,
        service='gas', unit='therms'):
    '''Returns approximate energy for the date interval [start_date, end_date)
    using per-day averages.'''
    return sum(daily_average_energy(reebill_dao, account, day, service=service,
        unit=unit) for day in dateutils.date_generator(start_date, end_date))

def monthly_average_energy(reebill_dao, account, year, month, service='gas',
        unit='therms'):
    return sum(daily_average_energy(reebill_dao, account, day, service=service,
        unit=unit) for day in calendar.itermonthdates(year, month))

def write_daily_average_energy_xls(reebill_dao, account, output_file,
        service='gas', unit='therms'):
    '''Writes an Excel spreadsheet to output_file showing average energy per
    day over all time. Time runs from top to bottom.'''
    reebills = reebill_dao.load_reebills_in_period(account)
    start = min(reebills, key=lambda x: x.period_begin).period_begin
    end = max(reebills, key=lambda x: x.period_end).period_end

    # spreadsheet setup
    workbook = xlwt.Workbook(encoding='utf-8')
    sheet = workbook.add_sheet(account)
    sheet.write(0, 0, 'Date')
    sheet.write(0, 1, 'Daily Average Energy from Utility Bills (%s)' % unit)
    row = 1

    # one row per day: date, energy
    for day in dateutils.date_generator(start, end):
        sheet.write(row, 0, day.isoformat())
        sheet.write(row, 1, daily_average_energy(reebill_dao, account, day,
            service, unit))
        row += 1
    workbook.save(output_file)


def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description='Generate reconciliation report.')
    parser.add_argument('--host',  default='localhost',
            help='host for all databases (default: localhost)')
    parser.add_argument('--billdb', default='skyline_dev',
            help='name of bill database (default: skyline_dev)')
    args = parser.parse_args()

    # set up config dicionaries for data access objects
    billdb_config = {
        'database': args.billdb,
        'collection': 'reebills',
        'host': args.host,
        'port': '27017'
    }
    reebill_dao = mongo.ReebillDAO(billdb_config)
    print daily_average_energy(reebill_dao, '10001', date(2011, 1, 1))
    print daily_average_energy(reebill_dao, '10001', date(2011, 1, 1), unit='btu')
    print daily_average_energy(reebill_dao, '10001', date(2011, 1, 1), unit='kwh')
    print monthly_average_energy(reebill_dao, '10001', 2011, 1)
    print average_energy_for_date_range(reebill_dao, '10001', date(2010,10,1), date(2011,6,1))

if __name__ == '__main__':
    main()
