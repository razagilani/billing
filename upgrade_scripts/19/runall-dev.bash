#!/bin/bash
mysql -udev -pdev -Dskyline_dev < 01_customer_recipient.sql
python 02_reebill_mysql.py --statedbhost localhost --statedbname skyline_dev --statedbuser dev --statedbpasswd dev --billdbhost localhost --billdbname skyline-dev
python 03_merge_rs.py --statedbhost localhost --statedbname skyline_dev --statedbuser dev --statedbpasswd dev --billdbhost localhost --billdbname skyline-dev
python 04_charge_groups.py --billdbhost localhost --billdbname skyline-dev
python 05_rename_utilbills.py --statedbhost localhost --statedbname skyline_dev --statedbuser dev --statedbpasswd dev --utilitybillpath "/db-dev/skyline/utilitybills/"

