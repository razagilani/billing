#!/bin/bash

now=`date +"%Y%m%d"`
cd /tmp
# destage
mysql --verbose -uroot -pvLGhTZu9eq4ULvbbKzlE -D skyline_stage < ${now}billing_mysql.dmp
mongorestore --drop --db skyline-stage --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline-stage --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline-stage --collection utilbills ${now}utilbills_mongo/skyline-prod/utilbills.bson
mongorestore --drop --db skyline-stage --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline-stage --collection users ${now}users_mongo/skyline-prod/users.bson
rm -r /db-stage/*
cp -r /db-prod/* /db-stage
