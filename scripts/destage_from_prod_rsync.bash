#!/bin/bash

USAGE="
Usage: $0 -n -s PRODHOST TOENV MYSQLPASSWORD
     De-stages production ReeBill data to the specified environment.

     -n -- optional, no download, use already downloaded database data if exists, default is to always download. 
     -s -- optional, skip bill syncing, default is to always sync bill pdfs.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. skyline-internal-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     MYSQLPASSWORD -- local mysql admin password
     "

NODOWNLOAD=false
SKIPBILLS=false
while getopts "ns" opt; do
    case $opt in
        n)
            echo -e "\nUsing already downloaded data, if it exists\n"
            NODOWNLOAD=true
            ;;
        s)
            echo -e "\nSkipping bill download, bill pdfs will not be updated\n"
            SKIPBILLS=true
            ;;
        \?)
            echo -e "\ninvalid option ($OPTARG), ignoring\n"
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
# Save current directory to CD back to it
current_dir="$( cd "$( dirname "$0" )" && pwd)"

cd /tmp
if [ "$NODOWNLOAD" = "false" ]
then # -n not given
    echo -e "\nDownloading database dump files.\n"
    rsync -ahz --exclude 'db-prod' --progress -e "ssh" $PRODHOST:/tmp/$destage_dir . 
elif [ ! -d ${now}reebill-prod ] # -n given, dir doesnt exist
then
    echo -e "\nDownloading database dumps one time, future use with -n will use this download.\n"
    rsync -ahz --exclude 'db-prod' --progress -e "ssh" $PRODHOST:/tmp/$destage_dir . 
else
    echo -e "\nNot Downloading data, already exists\n"
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
    echo -e "\nSyncing bill pdfs..."
    rsync -ahz --progress -e "ssh" $PRODHOST:/tmp/${now}reebill-prod/db-prod/ /db-$TOENV
fi
