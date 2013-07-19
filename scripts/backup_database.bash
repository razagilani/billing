#!/bin/bash

USAGE="
Usage: $0 ENVNAME SQLPASSWORD
     Creates a backup of the specified database
     MYSQLPASSWORD -- mysql admin password
     ENVNAME -- parameter specifying the environment to be backed up (e.g. stage, dev).
     "

: ${1?"$USAGE"} 

if [ $# -ne 2 ]; then
    echo "Specify args."
    exit 1
fi

MYSQLPASSWORD=$2
DBENV=$1

# backup 
now=`date +"%Y%m%d"`
cd /tmp

# unbounded file creation if backup script starts accidently running more than once a day as is want to happen in cron
if [ -d "${now}reebill-$DBENV" ]; then
    hour=`date +"%H-%M"`
    mv ${now}reebill-$DBENV ${now}reebill-$DBENV-${hour}
fi

mkdir ${now}reebill-$DBENV
cd  ${now}reebill-$DBENV
#P4IMvFI9DRTd
mysqldump -uroot -p$MYSQLPASSWORD skyline_$DBENV > ${now}billing_mysql.dmp
mongodump --db skyline-$DBENV --collection ratestructure --out ${now}ratestructure_mongo
mongodump --db skyline-$DBENV --collection reebills --out ${now}reebills_mongo
mongodump --db skyline-$DBENV --collection utilbills --out ${now}utilbills_mongo
mongodump --db skyline-$DBENV --collection journal --out ${now}journal_mongo
mongodump --db skyline-$DBENV --collection users --out ${now}users_mongo
cp -r /db-$DBENV .
cd /tmp
tar czvf ${now}reebill-$DBENV.tar.z ${now}reebill-$DBENV 
