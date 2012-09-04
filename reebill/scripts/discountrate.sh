#!/bin/bash
# Prints a CSV of each customer's reebill account number, name, and discount rate.
HOST=tyrell
DB=skyline_prod
USER=reebill-prod
PW=AXUPU4XGMSN
QUERY="use $DB; select account, name, discountrate from customer;"
AWK='BEGIN { print "Account,Name,Discount Rate"} NR>1 {printf "%s,%s,%s\n", $1, $2, $3 }'
echo "$QUERY" | mysql -h$HOST -u$USER -p$PW | sort -n | awk -F '\t' "$AWK"
