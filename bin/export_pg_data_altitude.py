#!/usr/bin/env python
"""Script to generate CSV file with data described in "Billing 24" Google
doc. Can be executed by cron.

This file doesn't/shouldn't have test coverage so don't put substantive code
in it!
"""
from sys import stdout
from argparse import ArgumentParser
from uuid import uuid4
from core import init_config, init_model
from core import altitude
from brokerage.export_altitude import PGAltitudeExporter, _load_pg_utilbills,\
    _create_brokerage_accounts_for_utility_accounts

if __name__ == '__main__':
    init_config()
    init_model()
    _create_brokerage_accounts_for_utility_accounts()
    pgae = PGAltitudeExporter(uuid4, altitude)
    print _load_pg_utilbills().count()
    pgae.write_csv(_load_pg_utilbills(), stdout)
