#!/bin/bash
# Convenience script to delete/recreate database, destage data, and run all upgrade scripts. Not to be used in production!
set -e
scripts_dir=`dirname $0`
echo 'drop database if exists skyline_dev; create database skyline_dev; grant all on skyline_dev.* to dev;' | mysql -uroot -proot
echo "******************************************************** destaging db"
$scripts_dir/../../scripts/destage_from_prod_rsync.bash tyrell-prod dev root
echo "******************************************************** cleanup"
for file in $scripts_dir/cleanup/*; do
    python $file;
done
echo "******************************************************** 01_urs.py"
python $scripts_dir/01_urs.py
echo "******************************************************** 02_manymany.sql"
mysql -uroot -proot -Dskyline_dev < $scripts_dir/02_manymany.sql
echo "******************************************************** 03_reebill_schema.py"
python $scripts_dir/03_reebill_schema.py
echo "******************************************************** 04_fix_view.sql"
mysql -uroot -proot -Dskyline_dev < $scripts_dir/04_fix_view.sql
echo "******************************************************** 05_unfreeze.py"
python $scripts_dir/05_unfreeze.py
echo "******************************************************** 06_utilbill_id_utility_rs.py"
python $scripts_dir/06_utilbill_id_utility_rs.py
echo "******************************************************** 07_rs_ids.py"
python $scripts_dir/07_rs_ids.py
echo "******************************************************** 08_issue_dates.py"
python $scripts_dir/08_issue_dates.py
