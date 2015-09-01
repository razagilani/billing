#!/bin/bash

# This file takes emails from stdin, sets up a python virtual 
# environment, and pipes the content of the file to the bill
# matrix importer application.  This file should be used 
# together with Postfix.  An email alias can be created to 
# pipe incoming email to this script.

#Receive input from stdin.
input="$1"

#Set up the python virtual environment
VIRT_PYTHON="/var/local/reebill-dev/bin/python"
VIRT_FILE="/var/local/reebill-dev/billing/bin/receive_matrix_email.py"
export PYTHONPATH=/var/local/reebill-dev/billing:/var/local/reebill-dev/lib/python2.7/site-packages:/var/local/reebill-dev/lib/python2.7/dist-packages:
source /var/local/reebill-dev/bin/activate

#Output the contents of stdin to the python application
cat $input | $VIRT_PYTHON $VIRT_FILE
