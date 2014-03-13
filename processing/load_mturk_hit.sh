#!/bin/bash
export JAVA_HOME=/usr/lib/jvm/jre
cd /tmp/aws-mturk-clt-1.3.1/bin
./loadHITs.sh -sandbox -properties $2 -input /tmp/slices/$1.input -question /tmp/slices/$1.question -label /tmp/slices/$1
