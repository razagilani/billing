#!/bin/bash

export JAVA_HOME=/usr/local/java/jre1.7.0_40
cd /tmp/aws-mturk-clt-1.3.1/bin
./getResults.sh -outputfile /tmp/slices/$1.results -successfile /tmp/slices/$1.success
