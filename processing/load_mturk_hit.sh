#!/bin/bash

export JAVA_HOME=/usr/local/java/jre1.7.0_40
cd /tmp/aws-mturk-clt-1.3.1/bin
echo $1
echo $2
./loadHITs.sh -properties $2 -input /tmp/slices/$1.input -question /tmp/slices/$1.question -label /tmp/slices/$1
