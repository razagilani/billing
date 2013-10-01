#!/bin/bash
# Convenience script to delete/recreate database, destage data, and run all upgrade scripts. Not to be used in production!
set -e
echo 'drop database if exists skyline_dev; create database skyline_dev; grant all on skyline_dev.* to dev;' | mysql -uroot -proot
echo "******************************************************** destaging db"
../../scripts/destage_from_prod_rsync.bash tyrell-prod dev root
echo "******************************************************** cleanup"
for file in cleanup/*; do
    python $file;
done
echo "******************************************************** 01_urs.py"
python 01_urs.py
echo "******************************************************** 02_manymany.sql"
mysql -uroot -proot -Dskyline_dev < 02_manymany.sql
echo "******************************************************** 03_reebill_schema.py"
python 03_reebill_schema.py
echo "******************************************************** 04_fix_view.sql"
mysql -uroot -proot -Dskyline_dev < 04_fix_view.sql
echo "******************************************************** 05_unfreeze.py"
python 05_unfreeze.py
echo "******************************************************** 06_utilbill_id_utility_rs.py"
python 06_utilbill_id_utility_rs.py
echo "******************************************************** 07_rs_ids.py"
python 07_rs_ids.py
echo "******************************************************** 08_issue_dates.py"
python 08_issue_dates.py
