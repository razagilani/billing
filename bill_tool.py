#!/usr/bin/python

#
# runtime environment
#

# handle command line options
from optparse import OptionParser
from billing.presentation import render_bill as rb
from billing.processing import process as p

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("--mode", dest="mode", help="process|render")

    # old render_bill options (now render.py)
    parser.add_option("-s", "--snob", dest="snob", help="Convert bill to PDF", metavar="FILE")
    parser.add_option("-o", "--output", dest="output", help="PDF output file", metavar="FILE")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Print progress to stdout.")
    parser.add_option("-b", "--background", dest="background", default="EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png", help="Background file names in comma separated page order. E.g. -b foo-page1.png,foo-page2.png")

    # old bill_tool options (now process.py)
    parser.add_option("--inputbill", dest="inputbill", help="Previous bill to acted on", metavar="FILE")
    parser.add_option("--outputbill", dest="outputbill", help="Next bill to be targeted", metavar="FILE")
    parser.add_option("-a", "--amountpaid", dest="amountpaid", help="Amount paid on previous bill")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")
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

    (options, args) = parser.parse_args()

    if (options.mode == "render"):

        # handle render options
        if (options.snob == None):
            print "SNOB must be specified."
            exit()

        if (options.output == None):
            print "Output file must be specified."
            exit()

        rb.main(options)

    # handle process options 
    elif (options.mode == "process"):

        if (options.inputbill == None):
            print "Input bill must be specified."
            exit()

        if (options.outputbill == None):
            print "Output bill must be specified"
            exit()

        if (options.roll):
            # TODO: remove this check to the roll function, and have that function return status based on this check below
            if (options.inputbill == options.outputbill):
                print "Input bill and output bill should not match!"
                exit()
            if (options.amountpaid == None):
                print "Specify --amountpaid"
                exit()
            else:
                Process().roll_bill(options.inputbill, options.outputbill, options.amountpaid, options.user, options.password)
                exit()

        if (options.sumhypothetical):
            Process().sum_hypothetical_charges(options.inputbill, options.outputbill, options.user, options.password)
            exit()

        if (options.copyactual):
            Process().copy_actual_charges(options.inputbill, options.outputbill, options.user, options.password)
            exit()

        if (options.sumactual):
            Process().sum_actual_charges(options.inputbill, options.outputbill, options.user, options.password)
            exit()

        if (options.sumbill):
            if (options.discountrate):
                Process().sumbill(options.inputbill, options.outputbill, options.discountrate, options.user, options.password)
            else:
                print "Specify --discountrate"
            exit()

        if (options.bindrsactual):
            if (options.rsdb == None):
                print "Specify --rsdb"
                exit()
            Process().bindrs(options.inputbill, options.outputbill, options.rsdb, False, options.user, options.password)
            exit()

        if (options.bindrshypothetical):
            if (options.rsdb == None):
                print "Specify --rsdb"
                exit()
            Process().bindrs(options.inputbill, options.outputbill, options.rsdb, True, options.user, options.password)
            exit()

        if (options.calcstats):
            if (options.inputbill == options.outputbill):
                # TODO: remove this check to the calcstats function, and have that function return status based on this check below
                print "Input bill and output bill should not match! Specify previous bill as input bill."
                exit()
            Process().calculate_statistics(options.inputbill, options.outputbill, options.user, options.password)
            exit()

        if (options.calcreperiod):
            # TODO: remove this check to the calcreperiods function, and have that function return status based on this check below
            if (options.inputbill != options.outputbill):
                print "Input bill and output bill should match!"
                exit()
            Process().calculate_reperiod(options.inputbill, options.outputbill, options.user, options.password)
            exit()

        if (options.issuedate):
            if (options.inputbill != options.outputbill):
                print "Input bill and output bill should match!"
                exit()
            if (options.issuedate == None):
                print "Specify --issuedate"
                exit()
            Process().issue(options.inputbill, options.outputbill, options.issuedate, options.user, options.password)
            exit()

        print "Specify Process Operation"
