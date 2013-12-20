#!/usr/bin/python
'''Creates a sample CSV file with random energy values every 15 minutes in the
format used by fetch_interval_meter_data. Command-line arguments are file name,
start date (ISO 8601, inclusive), end date (exclusive). E.g:
    make_sample_csv.py interval_meter_sample.csv 2012-11-10 2012-12-12
'''
import csv
import sys
import random
from datetime import date, datetime, timedelta
from billing import dateutils

# 10002-19, 2012-11-10 to 2011-12-12
# start_date = date(2012,11,10)
# end_date = date(2012,12,12)
start_date = datetime.strptime(sys.argv[2], dateutils.ISO_8601_DATE)
end_date = datetime.strptime(sys.argv[3], dateutils.ISO_8601_DATE)
with open(sys.argv[1], 'w') as csv_file:
    writer = csv.writer(csv_file)
    for day in dateutils.date_generator(start_date, end_date - timedelta(days=1)):
        dt = datetime(day.year, day.month, day.day, 0)
        while dt.day == day.day:
            dt += timedelta(hours=0.25)
            writer.writerow([
                datetime.strftime(dt, dateutils.ISO_8601_DATETIME),
                random.random(),
                'therms',
            ])


