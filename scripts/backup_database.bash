#!/bin/bash

USAGE="
Usage: $0 SQLPASSWORD ENVNAME
     Creates a backup of the specified database
     MYSQLPASSWORD -- mysql admin password
     ENVNAME -- parameter specifying the environment to be backed up (e.g. stage, dev).
     "

: ${1?"$USAGE"} 

if [ $# -ne 2 ]; then
    echo "Specify args."
    exit 1
fi

MYSQLPASSWORD=$1
DBENV=$2

# backup 
now=`date +"%Y%m%d"`
cd /tmp
mkdir ${now}reebill-$DBENV
cd  ${now}reebill-$DBENV

#P4IMvFI9DRTd
mysqldump -uroot -p$MYSQLPASSWORD --database skyline_$DBENV > ${now}billing_mysql.dmp
mongodump --db skyline-$DBENV --collection ratestructure --out ${now}ratestructure_mongo
mongodump --db skyline-$DBENV --collection reebills --out ${now}reebills_mongo
mongodump --db skyline-$DBENV --collection utilbills --out ${now}utilbills_mongo
mongodump --db skyline-$DBENV --collection journal --out ${now}journal_mongo
mongodump --db skyline-$DBENV --collection users --out ${now}users_mongo
cp -r /db-$DBENV .
cd /tmp
tar czvf ${now}reebill-$DBENV.tar.z /db-$DBENV ${now}reebill-$DBENV 
