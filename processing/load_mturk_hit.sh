#!/bin/bash

export JAVA_HOME=/usr/local/java/jre1.7.0_40
echo $0
echo $1
cd /tmp/aws-mturk-clt-1.3.1/bin
./loadHITs.sh -sandbox -properties ~/skyline-workspace/billing/processing/dla_templates/billImage.properties -input /tmp/slices/$1.input -question /tmp/slices/$1.question -label /tmp/slices/$2
