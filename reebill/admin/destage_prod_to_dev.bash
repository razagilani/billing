#!/bin/bash

USAGE="
Usage: $0 PRODHOST TOENV
     De-stages production ReeBill data to the specified environment.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. tyrell-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     "

# All SaaS environments (yourhost.yourdomain.com) are additionally named within the *.skylineinnovations.net DNS namespace
# therefore, hosts do not need to be qualified with skylineinnovations.net

: ${1?"$USAGE"} 

if [ $# -ne 2 ]; then
    echo "Specify args."
    exit 1
fi
PRODHOST=$1 
TOENV=$2

# Script to restore development MySQL, Mongo collections, and filesystem from
# backups on tyrell-prod. Based on billing/reebill/admin/destage.bash.
now=`date +"%Y%m%d"`
# need to more uniquely name backup file
tarball=${now}reebill-prod.tar.z
ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem

cd /tmp

if [ -f $tarball ]
then
    echo "Using previously downloaded $tarball"
else
    scp -i $ssh_key ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$tarball .
    tar xzf $tarball
fi
# apparently only root can restore the database?
# "Access denied; you need the SUPER privilege for this operation"
mysql -uroot -proot -D skyline_$TOENV < ${now}billing_mysql.dmp

# restore
mongorestore --drop --db skyline-$TOENV --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline-$TOENV --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline-$TOENV --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline-$TOENV --collection users ${now}users_mongo/skyline-prod/users.bson
mongorestore --drop --db skyline-$TOENV --collection utilbills ${now}users_mongo/skyline-prod/utilbills.bson

# delete local bill files and replace with destaged copy
rm -fr /db-$TOENV/*
cp -r db-prod/* /db-$TOENV
