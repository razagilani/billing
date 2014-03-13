#!/bin/bash
export JAVA_HOME=/usr/lib/jvm/jre
cd /tmp/aws-mturk-clt-1.3.1/bin
./getResults.sh -sandbox -outputfile /tmp/slices/$1.results -successfile /tmp/slices/$1.success
