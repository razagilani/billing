#!/bin/bash
mysql -ureebill-demo -p6DR1dBm8hGfAlxh -Dskyline_demo < 01_customer_recipient.sql
python 02_reebill_mysql.py --statedbhost localhost --statedbname skyline_demo --statedbuser reebill-demo --statedbpasswd 6DR1dBm8hGfAlxh --billdbhost localhost --billdbname skyline-demo
python 03_merge_rs.py --statedbhost localhost --statedbname skyline_demo --statedbuser reebill-demo --statedbpasswd 6DR1dBm8hGfAlxh --billdbhost localhost --billdbname skyline-demo
python 04_charge_groups.py --billdbhost localhost --billdbname skyline-demo
python 05_rename_utilbills.py --statedbhost localhost --statedbname skyline_demo --statedbuser reebill-demo --statedbpasswd 6DR1dBm8hGfAlxh --utilitybillpath "/db-demo/skyline/utilitybills/"
