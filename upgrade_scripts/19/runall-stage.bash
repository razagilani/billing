#!/bin/bash
mysql -ureebill-stage -pKdvDzFZeawPy -Dskyline_stage < 01_customer_recipient.sql
python 02_reebill_mysql.py --statedbhost localhost --statedbname skyline_stage --statedbuser reebill-stage --statedbpasswd KdvDzFZeawPy --billdbhost localhost --billdbname skyline-stage
python 03_merge_rs.py --statedbhost localhost --statedbname skyline_stage --statedbuser reebill-stage --statedbpasswd KdvDzFZeawPy --billdbhost localhost --billdbname skyline-stage
python 04_charge_groups.py --billdbhost localhost --billdbname skyline-stage
python 05_rename_utilbills.py --statedbhost localhost --statedbname skyline_stage --statedbuser reebill-stage --statedbpasswd KdvDzFZeawPy --utilitybillpath "/db-stage/skyline/utilitybills/"
