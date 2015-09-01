#!/bin/bash

# This file takes emails from stdin, sets up a python virtual 
# environment, and pipes the content of the file to the bill
# matrix importer application.  This file should be used 
# together with Postfix.  An email alias can be created to 
# pipe incoming email to this script.

#Set up the python virtual environment
source ~<%= @username%>/.bash_profile

#Output the contents of stdin to the python application
VIRT_FILE="/var/local/<%= @username%>/billing/bin/receive_matrix_email.py"
./$VIRT_FILE < $1
