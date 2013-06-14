#!/bin/bash

# backup 
now=`date +"%Y%m%d"`
cd /tmp
mysqldump -uroot -pP4IMvFI9DRTd skyline_prod > ${now}billing_mysql.dmp
mongodump --db skyline-prod --collection ratestructure --out ${now}ratestructure_mongo
mongodump --db skyline-prod --collection reebills --out ${now}reebills_mongo
mongodump --db skyline-prod --collection utilbills --out ${now}utilbills_mongo
mongodump --db skyline-prod --collection journal --out ${now}journal_mongo
mongodump --db skyline-prod --collection users --out ${now}users_mongo

# store these in their own folder
mkdir ${now}reebill-prod
mv -r /db-prod ${now}reebill-prod
mv ${now}billing_mysql.dmp ${now}reebill-prod;
mv -r ${now}ratestructure_mongo ${now}reebill-prod;
mv -r ${now}reebills_mongo ${now}reebill-prod;
mv -r ${now}utilbills_mongo ${now}reebill-prod;
mv -r ${now}journal_mongo ${now}reebill-prod;
mv -r ${now}users_mongo ${now}reebill-prod;
#tar czvf ${now}reebill-prod.tar.z /db-prod ${now}ratestructure_mongo ${now}reebills_mongo ${now}users_mongo ${now}billing_mysql.dmp ${now}journal_mongo ${now}utilbills_mongo

# permanently store a backup every friday
#if [ `date +"%w"` -eq 5 ]; then 
#mkdir /home/reebill-prod/${now}reebill-prod
#cp -r /db-prod /home/reebill-prod/${now}reebill-prod
#cp ${now}billing_mysql.dmp /home/reebill-prod/${now}reebill-prod;
#cp -r ${now}ratestructure_mongo /home/reebill-prod/${now}reebill-prod;
#cp -r ${now}reebills_mongo /home/reebill-prod/${now}reebill-prod;
#cp -r ${now}utilbills_mongo /home/reebill-prod/${now}reebill-prod;
#cp -r ${now}journal_mongo /home/reebill-prod/${now}reebill-prod;
#cp -r ${now}users_mongo /home/reebill-prod/${now}reebill-prod;
#fi
