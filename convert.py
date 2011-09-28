#!/usr/bin/python

from mongo import ReebillDAO
from processing.process import Process
from processing.rate_structure import RateStructureDAO
from processing.state import StateDB

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

    process = Process({}, state_db, reebill_dao, ratestructure_dao)


    success_count = 0
    error_count = 0
    for account in range(10001, 10025):
        for sequence in range(1,20):
            try:

                # convert to mongo
                reebill = reebill_dao.load_reebill(account, sequence)

                # convert rate structure
                process.bind_rate_structure(reebill)

                reebill_dao.save_reebill(reebill)

                success_count += 1
            except AttributeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
            except TypeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
            except IOError:
                pass
    print 'imported %s bills' % success_count
    print error_count, 'errors'



