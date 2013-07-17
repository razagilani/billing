#!/bin/bash -v

USAGE="
Usage: $0 PRODHOST TOENV MYSQLPASSWORD -n 
     De-stages production ReeBill data to the specified environment.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. tyrell-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     MYSQLPASSWORD -- local mysql admin password
     -n -- optional, use already downloaded files, skipping rsync 
             
     "
# All SaaS environments (yourhost.yourdomain.com) are additionally named within the *.skylineinnovations.net DNS namespace
# therefore, hosts do not need to be qualified with skylineinnovations.net

: ${1?"$USAGE"} 

if [ $# -lt 3 ]; then
    echo "Specify args."
    exit 1
fi

PRODHOST=$1 
TOENV=$2
MYSQLPASSWORD=$3
RSYNC=$4

# need to more uniquely name backup file
now=`date +"%Y%m%d"`
destage_dir=${now}reebill-prod
ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem
# Save current directory to CD back to it
current_dir="$( cd "$( dirname "$0" )" && pwd)"

cd /tmp
if [ -z $RSYNC ] || [ $RSYNC != '-n' ]
then
    rsync -ahz --exclude 'db-prod' --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir . 
else
    echo "Skipping file download due to -n flag"
fi
cd ${now}reebill-prod

# apparently only root can restore the database
mysql -uroot -p$MYSQLPASSWORD -e "create database if not exists skyline_${TOENV};"
mysql -uroot -p$MYSQLPASSWORD -D skyline_$TOENV < ${now}billing_mysql.dmp

# restore mongo collections
mongorestore --drop --db skyline-$TOENV --collection ratestructure ${now}ratestructure_mongo/skyline-prod/ratestructure.bson
mongorestore --drop --db skyline-$TOENV --collection reebills ${now}reebills_mongo/skyline-prod/reebills.bson
mongorestore --drop --db skyline-$TOENV --collection journal ${now}journal_mongo/skyline-prod/journal.bson
mongorestore --drop --db skyline-$TOENV --collection users ${now}users_mongo/skyline-prod/users.bson
mongorestore --drop --db skyline-$TOENV --collection utilbills ${now}utilbills_mongo/skyline-prod/utilbills.bson

# Scrub Mongo of customer data
cd $current_dir
mongo --eval "conn = new Mongo(); db = conn.getDB('skyline-$TOENV');" scrub_prod_data.js
