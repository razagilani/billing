#!/usr/bin/python

from mongo import ReebillDAO
from processing.process import Process
from processing.rate_structure import RateStructureDAO
from processing.state import StateDB

import pdb

if __name__ == '__main__':

    ratestructure_dao = RateStructureDAO({
        "database":"skyline",
        "rspath":"/db-dev/skyline/ratestructure/",
        "host":"localhost",
        "collection":"ratestructure",
        "port": 27017
    })

    state_db = StateDB({
        "host": "localhost",
        "password": "dev",
        "db": "skyline",
        "user": "dev"
    }) 

    reebill_dao = ReebillDAO({
        "host":"localhost", 
        "port":27017, 
        "database":"skyline", 
        "collection":"reebills", 
        "destination_prefix":"http://localhost:8080/exist/rest/db/skyline/bills"
    })

    #process = Process({}, state_db, reebill_dao, ratestructure_dao)

    success_count = 0
    error_count = 0
    pdb.set_trace()
    for account in range(10001, 10025):
        for sequence in range(1,20):
            try:

                # convert to mongo
                reebill = reebill_dao.load_reebill(account, sequence)
                reebill_dao.save_reebill(reebill)

                success_count += 1
            except AttributeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
            except TypeError as e:
                print '%s %s: %s' % (account, sequence,
                        'TypeError ' + str(e))
                error_count += 1
            except IOError:
                pass
            except Exception as e:
                print '%s %s: %s' % (account, sequence,
                        'Exception ' + str(e))
                error_count += 1

    print 'imported %s bills' % success_count
    print error_count, 'errors'

    success_count = 0
    error_count = 0

    print "************************************************"

    pdb.set_trace()

    for account in range(10001, 10025):
        for sequence in range(1,20):
            try:

                # convert to mongo
                reebill = reebill_dao.load_reebill(account, sequence)

                # convert rate structure
                ratestructure_dao.convert_rs_yaml(reebill)

                success_count += 1

                print 'Success: %s %s' % (account, sequence,)

            except AttributeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
            except TypeError as e:
                print '%s %s: %s' % (account, sequence,
                        'TypeError ' + str(e))
                error_count += 1
            except IOError as e:
                print '%s %s: %s' % (account, sequence,
                        'IOError ' + str(e))
                error_count += 1
            except Exception as e:
                print '%s %s: %s' % (account, sequence,
                        'Exception ' + str(e))
                error_count += 1

    print 'imported %s ratestructures' % success_count
    print error_count, 'errors'
