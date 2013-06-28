#!/bin/bash -v

USAGE="
Usage: $0 PRODHOST TOENV MYSQLPASSWORD
     De-stages production ReeBill data to the specified environment.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. tyrell-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     MYSQLPASSWORD -- local mysql admin password
     "

# All SaaS environments (yourhost.yourdomain.com) are additionally named within the *.skylineinnovations.net DNS namespace
# therefore, hosts do not need to be qualified with skylineinnovations.net

: ${1?"$USAGE"} 

if [ $# -ne 3 ]; then
    echo "Specify args."
    exit 1
fi

MYSQLPASSWORD=$3
PRODHOST=$1 
TOENV=$2

# Script to restore development MySQL, Mongo collections, and filesystem from
# backups on tyrell-prod. Based on billing/reebill/admin/destage.bash.
now=`date +"%Y%m%d"`
# need to more uniquely name backup file
destage_dir=${now}reebill-prod
ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem
# Save current directory to CD back to it
current_dir="$( cd "$( dirname "$0" )" && pwd)"

cd /tmp

#rsync -ahz --exclude 'db_prod' --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}billing_mysql.dmp . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}ratestructure_mongo . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}reebills_mongo . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}journal_mongo . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}users_mongo . 
rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/$destage_dir/${now}utilbills_mongo . 

# apparently only root can restore the database
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
