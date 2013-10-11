#!/bin/bash

USAGE="
Usage: $0 PRODHOST TOENV MYSQLPASSWORD -n -s
     De-stages production ReeBill data to the specified environment.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. tyrell-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     MYSQLPASSWORD -- local mysql admin password
     -n -- optional, no download, use already downloaded database data if exists, default is to always download. 
     -s -- optional, skip bill syncing, default is to always sync bill pdfs.
     "

NODOWNLOAD=false
SKIPBILLS=false
while getopts "ns" opt; do
    case $opt in
        n)
            echo "Using already downloaded data, if it exists"
            NODOWNLOAD=true
            ;;
        s)
            echo "Skipping bill download, bill pdfs will not be updated"
            SKIPBILLS=true
            ;;
        \?)
            echo "invalid option ($OPTARG), ignoring"
            ;;
    esac
done
shift $((OPTIND-1))


: ${1?"$USAGE"} 

if [ $# -lt 3 ]; then
    echo "Specify args."
    exit 1
fi

PRODHOST=$1 
TOENV=$2
MYSQLPASSWORD=$3

# need to more uniquely name backup file
now=`date +"%Y%m%d"`
destage_dir=${now}reebill-prod
ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem
# Save current directory to CD back to it
current_dir="$( cd "$( dirname "$0" )" && pwd)"

cd /tmp
if [ "$NODOWNLOAD" = "false" ]
then # -n not given
    rsync -ahz --exclude 'db-prod' --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir . 
elif [ ! -d ${now}reebill-prod ] # -n given, dir doesnt exist
then
    rsync -ahz --exclude 'db-prod' --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir . 
    echo "Downloading database dumps one time, future use with -n will use this download."
else
    echo "Not Downloading data, already exists"
fi
cd ${now}reebill-prod

# apparently only root can restore the database
mysql -uroot -p$MYSQLPASSWORD -e "drop database if exists skyline_${TOENV}"
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

if [ "$SKIPBILLS" = "false" ]
then
    rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/${now}reebill-prod/db-prod/ /db-$TOENV
fi
