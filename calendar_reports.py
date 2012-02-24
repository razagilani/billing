#!/usr/bin/python
'''Reports that involve averaging utility bill total energy over the bill period.'''
import traceback
import argparse
from datetime import date, timedelta
from calendar import Calendar
from decimal import Decimal
from billing import mongo
from billing import dateutils

calendar = Calendar()

def daily_average_energy(reebill_dao, account, day, service='Gas', unit='therms'):
    # find out what reebill covers this day and has a utility bill of the right
    # service that covers day
    # TODO put method in ReebillDAO to do this kind of query--needs to be fast
    # because this gets called repeatedly in monthly_average_energy
    possible_reebills = reebill_dao.load_reebills_in_period(account,
            start_date=day-timedelta(days=365),
            end_date=day+timedelta(days=365))
    reebill = None
    for possible_reebill in possible_reebills:
        if service in possible_reebill.services \
                and day >= possible_reebill.utilbill_period_for_service(service)[0] \
                and day < possible_reebill.utilbill_period_for_service(service)[1]:
            reebill = possible_reebill
            break
    if reebill is None:
        raise Exception("No reebills found for %s" % day)

    total_therms = 0
    meters = reebill.meters_for_service(service)
    for meter in meters:
        for register in meter['registers']:
            # TODO only include "total" registers, so we don't count things
            # like demand registers, etc. can we guarantee that there always is
            # a "total" register?
            if register['shadow'] == False:
                quantity = register['quantity']
                quantity_unit = register['quantity_units'].lower()
                if quantity_unit == 'therms':
                    total_therms += quantity
                elif quantity_unit == 'btu':
                    total_therms += quantity / Decimal(100000.0)
                elif quantity_unit == 'kwh':
                    total_therms += quantity / Decimal(.0341214163)
                elif quantity_unit == 'ccf':
                    raise Exception(("Register contains gas measured "
                        "in ccf: can't convert that into energy "
                        "without the multiplier."))
                else:
                    raise Exception('Unknown energy unit: "%s"' % \
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

def monthly_average_energy(reebill_dao, account, year, month, service='Gas', unit='therms'):
    total = 0
    for day in calendar.itermonthdates(year, month):
        total += daily_average_energy(reebill_dao, account, day,
                service=service, unit=unit)
    return total

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

if __name__ == '__main__':
    main()
