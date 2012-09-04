#!/bin/bash
# Script to restore development MySQL, Mongo collections, and filesystem from
# backups on tyrell-prod. Based on billing/reebill/admin/destage.bash.
now=`date +"%Y%m%d"`
tarball=${now}reebill-prod.tar.z
ssh_key=$HOME/Dropbox/IT/ec2keys/tyrell-prod.pem

cd /tmp

scp -i $ssh_key ec2-user@tyrell-prod.skylineinnovations.net:/tmp/$tarball .
tar xzf $tarball
# apparently only root can restore the database?
# "Access denied; you need the SUPER privilege for this operation"
mysql -uroot -proot -D skyline_dev < ${now}billing_mysql.dmp

# restore
mongorestore --drop --db skyline --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline --collection users ${now}users_mongo/skyline-prod/users.bson

# delete local bill files and replace with a copy from staging on tyrell-prod
rm -fr /db-dev/*
cp -r db-prod/* /db-dev
