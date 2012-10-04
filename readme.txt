This directory is the top level directory for items related to energy revenue billing.  It contains CLI, web applications, frameworks and supporting items such as documentation.

No code specific to any of these items should be located in this directory.


reebill - web app for processing bills
[new app1] - the next web app
[new app2] - the next CLI app
processing - framework of code used by one or more energy revenue/analysis programs
doc - doc
scripts - generic scripts applicable to all software in 'billing'
db - supporting scripts for underlying databases


stuff to put into reebill/scripts:
corrector.py
utilbill_histogram.py
graph.py
reconciliation.py

stuff to move into processing - a reebill specific lib
json_util.py
month_math.py
exceptions.py
mongo.py
users.py
excel_export
estimated revenue


questions
nexus_util.py - arguably skyliner level
dict_utils - general lib
dateutils.py - general lib
json_util - general lib - even necessary anymore?
mongo_utils - general lib
monthmath.py - probably still too close to reebill for general lib
holidays.py - maybe all date stuff should go into datelib
what should processing/ be renamed to?
