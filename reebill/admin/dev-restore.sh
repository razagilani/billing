#!/bin/bash
'''Script to restore development MySQL, Mongo collections, and filesystem from
backups on tyrell. Based on billing/reebill/admin/destage.bash. '''
now=`date +"%Y%m%d"`

# copy mysql dump file (generated last night via cron) from tyrell to local
# /tmp, then restore mysql dev database (which happens to be on tyrell) from
# that file
scp dklothe@tyrell:/tmp/${now}billing_mysql.dmp /tmp
mysql --verbose -udev -pdev -htyrell -D skyline_dev < /tmp/${now}billing_mysql.dmp
# TODO this script doesn't restore status_days_since--it must not be in the dump

# copy mongo dump files from tyrell to local /tmp and restore mongo collections from them
scp -r dklothe@tyrell:/tmp/${now}ratestructure_mongo /tmp
scp -r dklothe@tyrell:/tmp/${now}reebills_mongo /tmp
scp -r dklothe@tyrell:/tmp/${now}users_mongo /tmp

# TODO add more collections?
mongorestore --drop --db skyline --collection ratestructure /tmp/${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline --collection reebills /tmp/${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline --collection users /tmp/${now}users_mongo/skyline-prod/users.bson

# delete local bill files and replace with a copy from staging on tyrell
# (hopefully copied last night from production to staging)
#rm -rf /db-dev/
#scp -r dklothe@tyrell:/db-stage /db-dev
