#!/usr/bin/python
"""
Command line front end for processing and rendering bills.
"""

import os

# handle command line options
from optparse import OptionParser
from billing.presentation import render
from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd

if __name__ == "__main__":
    parser = OptionParser()

    # TODO: --inputbill and --outputbill should become --inputsource and --outputsource (or something)
    # and then create input as inputsource/account/sequence etc...
    parser.add_option("--source", dest="source", help="Source location of bill to acted on", metavar="FILE")
    parser.add_option("--destination", dest="destination", help="Destination location of bill to be targeted", metavar="FILE")

    parser.add_option("--account", dest="account", help="Customer billing account")
    parser.add_option("--sequence", dest="sequence", help="Bill sequence number")

    # username and password for web services & db
    parser.add_option("--user", dest="user", default='prod', help="User account name.")
    parser.add_option("--password", dest="password", help="User account name.")

    # TODO: merge -s and -o into --input and --output or something

    # Generate a PDF from bill xml
    parser.add_option("--render", action="store_true", dest="render", help="Render a bill")
    parser.add_option("-s", "--snob", dest="snob", help="Convert bill to PDF", metavar="FILE")
    parser.add_option("-o", "--output", dest="output", help="PDF output file", metavar="FILE")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Print progress to stdout.")
    parser.add_option("-b", "--background", dest="background", default="EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png", help="Background file names in comma separated page order. E.g. -b foo-page1.png,foo-page2.png")

    # Process bill
    parser.add_option("--amountpaid", dest="amountpaid", help="Amount paid on previous bill")
    parser.add_option("--roll", dest="roll", action="store_true", help="Roll the bill to the next period.")
    parser.add_option("--copyactual", action="store_true", dest="copyactual", help="Copy actual charges to hypothetical charges.")
    parser.add_option("--sumhypothetical", action="store_true", dest="sumhypothetical", help="Summarize hypothetical charges.")
    parser.add_option("--sumactual", action="store_true", dest="sumactual", help="Summarize actual charges.")
    parser.add_option("--sumbill", action="store_true", dest="sumbill", help="Calculate total due.")
    parser.add_option("--discountrate",  dest="discountrate", help="Customer energy discount rate from 0.0 to 1.0")
    parser.add_option("--bindrsactual", action="store_true", dest="bindrsactual", help="Bind and evaluate a rate structure.")
    parser.add_option("--bindrshypothetical", action="store_true", dest="bindrshypothetical", help="Bind and evaluate a rate structure.")
    parser.add_option("--rsdb", dest="rsdb", help="Location of the rate structure database.")
    parser.add_option("--calcstats", action="store_true", dest="calcstats", help="Calculate statistics.")
    parser.add_option("--calcreperiod", action="store_true", dest="calcreperiod", help="Calculate Renewable Energy Period.")
    # TODO: make this commit the bill, parameterize due date, etc...
    parser.add_option("--issuedate",  dest="issuedate", help="Set the issue and due dates of the bill. Specify issue date YYYY-MM-DD")

    # state db for processing
    parser.add_option("--host", dest="dbhost")
    parser.add_option("--database", dest="database")
    parser.add_option("--commit", action="store_true", dest="commit", help="Update bill in state db as processed")
    parser.add_option("--begin", dest="begin", help="RE bill period begin")
    parser.add_option("--end", dest="end", help="RE bill period end")

    # fetch bill data
    parser.add_option("--fetch", action="store_true", dest="fetch", help="Fetch bill data")
    parser.add_option("--olap", dest="olap_id", help="Bind to data from olap NAME. e.g. daves ", metavar="NAME")
    # ToDo: bind to fuel type and begin period in bill 
    parser.add_option("--server", dest="server", default='http://duino-drop.appspot.com/', help="Location of a server that OLAP class Splinter() can use.")

    (options, args) = parser.parse_args()

    if (options.account == None):
        print "Account must be specified."
        exit()

    if (options.sequence == None):
        print "Sequence must be specified."
        exit()

    if (options.commit):
        # handle state db operations
        if (options.dbhost is None or options.database is None):
            print "Host and database must be specified"
            exit()
        if (options.begin is None or options.end is None):
            print "Utility bill period must be specified"
            exit()
        # TODO: snarf begin and end from bill itself
        state.commit_bill(options.dbhost, options.database, options.user, options.password, options.account, options.sequence, options.begin, options.end) 
        exit()

    if (options.source == None):
        print "Input bill must be specified."
        exit()

    if (options.destination == None):
        print "Using %s for output." % options.source
        options.destination = options.source

    if (options.calcstats):
        inputbill_xml = options.source + "/" + options.account + "/" + str(int(options.sequence)-1) + ".xml"
        outputbill_xml = options.destination + "/" + options.account + "/" + options.sequence + ".xml"
        process.Process().calculate_statistics(inputbill_xml, outputbill_xml, options.user, options.password)
        exit()

    # XML DB bill locations
    inputbill_xml = options.source + "/" + options.account + "/" + options.sequence + ".xml"

    # handle old fetch_bill_data
    if (options.fetch):
        fbd.fetch_bill_data(options.server, options.user, options.password, options.olap_id, inputbill_xml, options.begin, options.end, options.verbose)
        exit()


    if (options.render):

        if (options.destination == None):
            print "Destination must be specified."
            exit()

        # PDF system locations
        outputbill_pdf = os.path.join(options.destination, options.account, options.sequence + ".pdf")

        render.render(inputbill_xml, outputbill_pdf, options.background, options.verbose)
        exit()

    if (options.roll):
        if (options.destination == None):
            print "Destination must be specified."
            exit()

        if (options.amountpaid == None):
            print "Specify --amountpaid"
            exit()

        outputbill_xml = options.destination + "/" + options.account + "/" + str(int(options.sequence)+1) + ".xml"
        process.Process().roll_bill(inputbill_xml, outputbill_xml, options.amountpaid, options.user, options.password)
        exit()



    outputbill_xml = options.destination + "/" + options.account + "/" + options.sequence + ".xml"
    print "Output Bill XML Path " + outputbill_xml

    if (options.sumhypothetical):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        process.Process().sum_hypothetical_charges(inputbill_xml, outputbill_xml, options.user, options.password)
        exit()

    if (options.copyactual):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        process.Process().copy_actual_charges(inputbill_xml, outputbill_xml, options.user, options.password)
        exit()

    if (options.sumactual):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        process.Process().sum_actual_charges(inputbill_xml, outputbill_xml, options.user, options.password)
        exit()

    if (options.sumbill):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        if (options.discountrate):
            process.Process().sumbill(inputbill_xml, outputbill_xml, options.discountrate, options.user, options.password)
        else:
            print "Specify --discountrate"
        exit()

    if (options.bindrsactual):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        if (options.rsdb == None):
            print "Specify --rsdb"
            exit()
        process.Process().bindrs(inputbill_xml, outputbill_xml, options.rsdb, False, options.user, options.password)
        exit()

    if (options.bindrshypothetical):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        if (options.rsdb == None):
            print "Specify --rsdb"
            exit()
        process.Process().bindrs(inputbill_xml, outputbill_xml, options.rsdb, True, options.user, options.password)
        exit()


    if (options.calcreperiod):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        process.Process().calculate_reperiod(inputbill_xml, outputbill_xml, options.user, options.password)
        exit()

    if (options.issuedate):
        if (inputbill_xml != outputbill_xml):
            print "Input bill and output bill should be the same."
            exit()
        if (options.issuedate == None):
            print "Specify --issuedate"
            exit()
        process.Process().issue(inputbill_xml, outputbill_xml, options.issuedate, options.user, options.password)
        exit()

    print "Specify Process Operation"
