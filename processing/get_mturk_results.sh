#!/bin/bash

cd /tmp/aws-mturk-clt-1.3.1/bin
./getResults.sh -outputfile /tmp/slices/$1.results -successfile /tmp/slices/$1.success
