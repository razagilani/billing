#!/usr/bin/env python
'''Loads all reebills and their utility bills, prints errors and warnings if
bad or semi-bad conditions occur.'''
import pprint
from sys import stderr
from billing.exceptions import NotUniqueException
from billing.mongo import ReebillDAO
from billing.processing.state import StateDB
from billing.session_contextmanager import DBSession
pp = pprint.PrettyPrinter().pprint

# config parameters:
host = 'localhost'
db = 'skyline-dev' # mongo
statedb = 'skyline_dev' # mysql
user = 'dev'
password = 'dev'

# data-access objects:
sdb = StateDB(**{
    'host': host,
    'database': statedb,
    'password': password,
    'user': user,
})
dao = ReebillDAO(sdb, **{
    'host': host,
    'database': db,
    'port': 27017,
})

with DBSession(sdb) as session:

    # check that all utility bills can be loaded for each reebill
    for acc in sdb.listAccounts(session):
        for seq in sdb.listSequences(session, acc):
            max_version = sdb.max_version(session, acc, seq)
            for version in range(max_version + 1):

                try:
                    # load reebill (with frozen utility bills, if issued)
                    reebill = dao.load_reebill(acc, seq, version)

                    # load the un-frozen utility bills that are supposed to exist
                    # when this is the newest version of the bill (if the reebill
                    # is unissued, it will the same as the reebill above, but if
                    # it's not issued, it will be separate)
                    if version == max_version:
                        for u in reebill._utilbills:

                            # NOTE these keys don't HAVE to be unique, because the user
                            # could create 2 utility bills with the same dates. this
                            # was done for 10001-32-0/1 and 10001-33 (before 10001-33
                            # was deleted), and 10003-24,25.
                            try:
                                dao.load_utilbill(acc, u['service'], u['utility'],
                                        u['start'], u['end'], sequence=False,
                                        version=False)
                            except NotUniqueException as e:
                                print >> stderr, 'WARNING:', e

                except Exception as e:
                    print >> stderr, 'ERROR:', e
