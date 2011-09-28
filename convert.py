#!/usr/bin/python

from mongo import ReebillDAO

if __name__ == '__main__':

    # config data to be passed into ReebillDAO constructor when debugging
    config = {
        "host":"localhost", 
        "port":27017, 
        "database":"skyline", 
        "collection":"reebills", 
        "destination_prefix":"http://localhost:8080/exist/rest/db/skyline/bills"
    }

    dao = ReebillDAO(config)
    reebill = dao.load_reebill("10002","12")
    dao.save_reebill(reebill)

    success_count = 0
    error_count = 0
    for account in range(10001, 10025):
        for sequence in range(1,20):
            try:
                reebill = dao.load_reebill(account, sequence)
                dao.save_reebill(reebill)
                success_count += 1
            except AttributeError as e:
                print '%s %s: %s' % (account, sequence,
                        'AttributeError ' + str(e))
                error_count += 1
            except IOError:
                pass
    print 'imported %s bills' % success_count
    print error_count, 'errors'
