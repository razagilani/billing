#!/usr/bin/python

import yaml
import os
import rate_structure

if __name__ == "__main__":
    """ test code """

    #rs = yaml.load(file("/db/skyline/ratestructure/washgas/10005/9.yaml"))
    rs = yaml.load(file("test_rs_nobinding.yaml"))

    # instantiate the ratestructure
    rate_structure = rate_structure.RateStructure(rs)
