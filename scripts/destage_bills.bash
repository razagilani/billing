#!/bin/bash -v

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


# Script to restore development bill files from
# tyrell-prod.
PRODHOST=$1 
TOENV=$2

now=`date +"%Y%m%d"`

ssh_key=$HOME/Dropbox/IT/ec2keys/$PRODHOST.pem
# Save current directory to CD back to it
current_dir="$( cd "$( dirname "$0" )" && pwd)"

rsync -ahz --progress -e "ssh -i ${ssh_key}" ec2-user@$PRODHOST.skylineinnovations.net:/tmp/${now}reebill-prod/db-prod /db-$TOENV
cd $current_dir
