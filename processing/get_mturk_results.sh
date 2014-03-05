#!/bin/bash

export JAVA_HOME=/usr/local/java/jre1.7.0_40
echo $0
echo $1
cd /tmp/aws-mturk-clt-1.3.1/bin
./getResults.sh -sandbox -outputfile /tmp/slices/$1.results -successfile /tmp/slices/$1.success
