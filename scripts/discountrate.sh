#!/bin/bash
# Prints a CSV of each customer's reebill account number, name, and discount rate.
QUERY='use skyline_dev; select account, name, discountrate from customer;'
AWK='BEGIN { print "account,name,discountrate"} NR>1 {printf "%s,%s,%s\n", $1, $2, $3 }'
echo $QUERY | mysql -htyrell -udev -pdev | sort -n | awk -F '\t' "$AWK"
