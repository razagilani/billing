#!/bin/bash

# backup 
now=`date +"%Y%m%d"`
cd /tmp
mysqldump -uroot -pvLGhTZu9eq4ULvbbKzlE skyline_prod > ${now}billing_mysql.dmp
mongodump --db skyline-prod --collection ratestructure --out ${now}ratestructure_mongo
mongodump --db skyline-prod --collection reebills --out ${now}reebills_mongo

# compress
tar czvf ${now}reebill-prod.tar.z /db-prod ${now}ratestructure_mongo ${now}reebills_mongo

# permanently store a backup every friday
if [ `date +"%w"` -eq 5 ]; then 
cp ${now}reebill-prod.tar.z /home/reebill-prod;
fi
