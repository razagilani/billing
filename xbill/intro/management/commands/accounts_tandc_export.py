from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from xbill import settings
from intro.models import Account
import csv
import os.path
import logging


class Command(BaseCommand):
    help = 'Exports all accounts that have a guid and a TandC signed date'

    def handle(self, *args, **options):
        path = os.path.join(settings.XBILL_ETL_DIR,
                            settings.XBILL_ETL_ACCOUNTS_DIR,
                            'accounts.csv')
        log = logging.getLogger('xbill-etl')
        qs = Account.objects.exclude(
            Q(guid__isnull=True) | Q(tou_signed__isnull=True))
        rows = [(row.guid, row.tou_signed.isoformat(),
                 row.tou_version_signed) for row in qs]
        with open(path, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(('guid', 'opt-in 1 signed date',
                             'opt-in 1 version'))
            writer.writerows(rows)

        log.info("Wrote rows %s" % rows)
