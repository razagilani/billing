#!/bin/bash
# Script to restore development MySQL, Mongo collections, and filesystem from
# backups on tyrell. Based on billing/reebill/admin/destage.bash.
now=`date +"%Y%m%d"`
tarball=${now}reebill-prod.tar.z

cd /tmp

scp `whoami`@tyrell:/tmp/$tarball .
tar xvzf $tarball
# apparently only root can restore the database?
# "Access denied; you need the SUPER privilege for this operation"
mysql -uroot -proot -D skyline_dev < ${now}billing_mysql.dmp

# restore
mongorestore --drop --db skyline --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline --collection users ${now}users_mongo/skyline-prod/users.bson

# delete local bill files and replace with a copy from staging on tyrell
rm -fr /db-dev/*
cp -r db-prod/* /db-dev
