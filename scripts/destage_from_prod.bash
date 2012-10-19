#!/bin/bash -v

USAGE="
Usage: $0 MYSQLPASSWORD PRODHOST TOENV
     De-stages production ReeBill data to the specified environment.
     MYSQLPASSWORD -- local mysql admin password
     PRODHOST -- parameter specifying the hostname containing production data (e.g. tyrell-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     "

# All SaaS environments (yourhost.yourdomain.com) are additionally named within the *.skylineinnovations.net DNS namespace
# therefore, hosts do not need to be qualified with skylineinnovations.net

: ${1?"$USAGE"} 

if [ $# -ne 3 ]; then
    echo "Specify args."
    exit 1
fi

MYSQLPASSWORD=$1
PRODHOST=$2 
TOENV=$3

# Script to restore development MySQL, Mongo collections, and filesystem from
# backups on tyrell-prod. Based on billing/reebill/admin/destage.bash.
now=`date +"%Y%m%d"`
# need to more uniquely name backup file
tarball=${now}reebill-prod.tar.z
ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem

cd /tmp

if [ -f $tarball ]
then
    # TODO don't rely on presence of the tarball to determine whether the mongodump
    # directiories below also exist; they may not
    echo "Using previously downloaded $tarball"
else
    scp -i $ssh_key ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$tarball .
    tar xzf $tarball
fi

# apparently only root can restore the database
mysql -uroot -p$MYSQLPASSWORD -D skyline_$TOENV < ${now}billing_mysql.dmp

# restore mongo collections
mongorestore --drop --db skyline-$TOENV --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline-$TOENV --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline-$TOENV --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline-$TOENV --collection users ${now}users_mongo/skyline-prod/users.bson
mongorestore --drop --db skyline-$TOENV --collection utilbills ${now}utilbills_mongo/skyline-prod/utilbills.bson

# delete local bill files and replace with destaged copy
rm -fr /db-$TOENV/*
cp -r db-prod/* /db-$TOENV
