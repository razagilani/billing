#!/bin/bash

USAGE="
Usage: $0 PATH_TO_MANAGE.PY BACKUP.JSON
     Creates a Backup of the database. 
     !!   Must be run as the application user (xbill-prod/xbill-stage), with the virtualenv activated.  !!
        
     PATH_TO_MANAGE.PY -- Path to the manage.py file of the Django project
     BACKUP.JSON -- Path to the backup.json file
     "

: ${1?"$USAGE"} 

if [ $# -ne 2 ]; then
    echo "Specify args."
    echo "$USAGE"
    exit 1
fi

manage=$1
backup=$2

py=`which python2`

$py $manage loaddata $backup

