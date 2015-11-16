#!/bin/bash

USAGE="
Usage: $0 PATH_TO_MANAGE.PY
     Creates a Backup of the database. 
     !!   Must be run as the application user (xbill-prod/xbill-stage), with the virtualenv activated.  !!
     !!   Backups are stored as /tmp/[date]-backup.json                                                 !!
        
     PATH_TO_MANAGE.PY -- Path to the manage.py file of the Django project
     "

: ${1?"$USAGE"} 

if [ $# -ne 1 ]; then
    echo "Specify args."
    echo "$USAGE"
    exit 1
fi

manage=$1

py=`which python2`

# backup 
now=`date +"%Y%m%d"`

$py $manage dumpdata > /tmp/${now}-backup.json

