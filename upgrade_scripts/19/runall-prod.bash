#!/bin/bash
mysql -ureebill-prod -pNWH7H4wY -Dskyline_prod < 01_customer_recipient.sql
python 02_reebill_mysql.py --statedbhost localhost --statedbname skyline_prod --statedbuser reebill-prod --statedbpasswd NWH7H4wY --billdbhost localhost --billdbname skyline-prod
python 03_merge_rs.py --statedbhost localhost --statedbname skyline_prod --statedbuser reebill-prod --statedbpasswd NWH7H4wY --billdbhost localhost --billdbname skyline-prod
python 04_charge_groups.py --billdbhost localhost --billdbname skyline-prod
python 05_rename_utilbills.py --statedbhost localhost --statedbname skyline_prod --statedbuser reebill-prod --statedbpasswd NWH7H4wY --utilitybillpath "/db-prod/skyline/utilitybills/"
