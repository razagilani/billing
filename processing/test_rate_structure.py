#!/usr/bin/python

import yaml
import os
import rate_structure

if __name__ == "__main__":
    """ test code """

    #rs = yaml.load(file("/db/skyline/ratestructure/washgas/10005/9.yaml"))
    #rs = yaml.load(file("test_rs_nobinding.yaml"))
    #rs = yaml.load(file("test_rs_minimal.yaml"))
    #rs = yaml.load(file("test_rs_node_recursion.yaml"))
    #rs = yaml.load(file("test_rs_self_recursion.yaml"))
    rs = yaml.load(file("test_rs_noprop.yaml"))
    #rs = yaml.load(file("test_rs_badref.yaml"))
    #rs = yaml.load(file("test_rs_badsyntax.yaml"))

    # instantiate the ratestructure
    rate_structure = rate_structure.RateStructure(rs)
    #print rate_structure
    for rsi in rate_structure.rates:
        try:
            print "Calling %s.total" % (rsi.descriptor)
            print rsi.total
        except Exception as e:
            print "* caught %s exception for %s" % (type(e),rsi.descriptor)
            print "* " + str(e)
            continue;

