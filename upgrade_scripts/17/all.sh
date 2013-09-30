#!/bin/bash
# Convenience script to delete/recreate database, destage data, and run all upgrade scripts. Not to be used in production!
set -e
echo 'drop database if exists skyline_dev; create database skyline_dev; grant all on skyline_dev.* to dev;' | mysql -uroot -proot
echo "******************************************************** destaging db"
scripts/destage_from_prod_rsync.bash tyrell-prod dev root
echo "******************************************************** 01_urs.py"
python upgrade_scripts/17/01_urs.py
echo "******************************************************** 02_manymany.sql"
mysql -uroot -proot -Dskyline_dev < upgrade_scripts/17/02_manymany.sql
echo "******************************************************** 03_reebill_schema.py"
python upgrade_scripts/17/03_reebill_schema.py
echo "******************************************************** 04_fix_view.sql"
mysql -uroot -proot -Dskyline_dev < upgrade_scripts/17/04_fix_view.sql
echo "******************************************************** 05_unfreeze.py"
python upgrade_scripts/17/05_unfreeze.py
echo "******************************************************** 06_utilbill_id_utility_rs.py"
python upgrade_scripts/17/06_utilbill_id_utility_rs.py
echo "******************************************************** 07_rs_ids.py"
python upgrade_scripts/17/07_rs_ids.py
