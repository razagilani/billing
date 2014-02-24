#!/usr/bin/python

from mongo import ReebillDAO, NoRateStructureError, NoUtilityNameError
from processing.process import Process
from processing.rate_structure import RateStructureDAO
from processing.state import StateDB
from yaml.constructor import ConstructorError
import pdb

if __name__ == '__main__':
    ratestructure_dao = RateStructureDAO({
        "database":"skyline-[env]",
        "rspath":"/db-[env]/skyline/ratestructure/",
        "host":"localhost",
        "collection":"ratestructure",
        "port": 27017
    })

    state_db = StateDB({
        "host": "localhost",
        "password": "[password]",
        "db": "skyline_[env]",
        "user": "reebill-[env]"
    }) 

    reebill_dao = ReebillDAO({
        "host":"localhost", 
        "port":27017, 
        "database":"skyline-[env]", 
        "collection":"reebills", 
        "source_prefix":"http://localhost:8080/exist/rest/db/skyline/bills"
    })

    process = Process({}, state_db, reebill_dao, ratestructure_dao)

    success_count = 0
    error_count = 0
    for account in range(10001, 10025):
        for sequence in range(1,25):
            try:
                # convert to mongo
                reebill = reebill_dao.load_reebill(account, sequence)
                # convert rate structure
                #process.bind_rate_structure(reebill)
                reebill_dao.save_reebill(reebill)
                success_count += 1
                print 'Success: %s %s' % (account, sequence,)
            except NoRateStructureError as e:
                print '%s %s: no rate structure' % (account, sequence)
                error_count += 1
                raise
            except NoUtilityNameError as e:
                print '%s %s: no utility name' % (account, sequence)
                error_count += 1
                raise
            except AttributeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
                raise
            except TypeError as e:
                print '%s %s: %s' % (account, sequence,
                        'TypeError ' + str(e))
                error_count += 1
                raise
            except IOError as e:
                if str(e).endswith('failed to load HTTP resource'):
                    # there is no reebill for this account & sequence
                    pass
                else:
                    raise
            except Exception as e:
                print '%s %s: %s' % (account, sequence,
                        'Exception ' + str(e))
                error_count += 1
                raise
    print 'imported %s bills' % success_count
    print error_count, 'errors'

    print "************************************************"
    success_count = 0
    error_count = 0
    for account in range(10001, 10025):
        for sequence in range(1,25):
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
                raise
            except TypeError as e:
                print '%s %s: %s' % (account, sequence,
                        'TypeError ' + str(e))
                error_count += 1
                raise
            except IOError as e:
                if str(e).endswith('failed to load HTTP resource'):
                    # there is no reebill for this account & sequence
                    pass
                else:
                    print '%s %s: %s' % (account, sequence,
                            'IOError ' + str(e))
                    error_count += 1
            except Exception as e:
                print '%s %s: %s' % (account, sequence,
                        'Exception ' + str(e))
                error_count += 1
    print 'imported %s ratestructures' % success_count
    print error_count, 'errors'


