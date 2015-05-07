#!/bin/bash -v

USAGE="
Usage: $0 PRODHOST TOENV
     De-stages production ReeBill data to the specified environment.
     PRODHOST -- parameter specifying the hostname containing production data (e.g. skyline-internal-prod).
     TOENV -- parameter specifying the environment to be targeted by the de-stage (e.g. stage, dev).
     "

: ${1?"$USAGE"} 

if [ $# -ne 2 ]; then
    echo "Specify args."
    exit 1
fi


# Script to restore development bill files
PRODHOST=$1 
TOENV=$2

now=`date +"%Y%m%d"`

rsync -ahz --progress -e "ssh" $PRODHOST:/tmp/${now}reebill-prod/db-prod/ /db-$TOENV
