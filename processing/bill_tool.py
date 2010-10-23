#!/usr/bin/python
"""
File: bill_tool.py
Description: Various utility procedures to process bills
Usage: See command line synopsis
"""

#
# runtime support
#
import sys
import os  
from optparse import OptionParser

# for xml processing
from lxml import etree

from skyliner.xml_utils import XMLUtils

# for testing
#import StringIO

# used for processing fixed point monetary decimal numbers
from decimal import *

class BillTool():
    """ Class with a variety of utility procedures for processing bills """
    
    def __init__(self):
        pass

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    def get_elem(self, tree, xpath):
        return tree.xpath(xpath, namespaces={"ub":"bill"})


    # compute the value, charges and savings of renewable energy
    def sumbill(self, unprocessedBill, targetBill, discount_rate = None, user=None, password=None):

        tree = etree.parse(unprocessedBill)

        # obtain all of the utilbill groves 
        utilbills = self.get_elem(tree, "/ub:bill/ub:utilbill")
        for utilbill in utilbills:

            # determine the difference between the hypothetical and actual energy charges to determine revalue
            hypocharges = Decimal(self.get_elem(utilbill, "ub:hypotheticalecharges")[0].text)
            actualcharges = Decimal(self.get_elem(utilbill, "ub:actualecharges")[0].text)
            revalue = hypocharges - actualcharges
            self.get_elem(utilbill, "ub:revalue")[0].text = str(revalue)

            # we receive rounding down
            recharges = Decimal(self.get_elem(utilbill, "ub:revalue")[0].text) * Decimal(str(1.0 - float(discount_rate)))
            self.get_elem(utilbill, "ub:recharges")[0].text = str(recharges.quantize(Decimal('.00'), rounding=ROUND_DOWN))

            # customers receive rounding up
            resavings = Decimal(self.get_elem(utilbill, "ub:revalue")[0].text) * Decimal(str(discount_rate))
            self.get_elem(utilbill, "ub:resavings")[0].text = str(resavings.quantize(Decimal('.00'), rounding=ROUND_UP))

            # assert recharges + resavings = revalue
            assert(recharges + resavings == revalue)
        
        rebillrevalue = self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:revalue)")
        rebillrecharges = self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:recharges)")
        rebillresavings = self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:resavings)")

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:revalue")[0].text = str(rebillrevalue)
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:recharges")[0].text = str(rebillrecharges)
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:resavings")[0].text = str(rebillresavings)

        # totalize the bill
        # /ub:bill/ub:rebill/ub:totaldue = /ub:bill/ub:rebill/ub:totaladjustment + /ub:bill/ub:rebill/ub:balanceforward + 
        # /ub:bill/ub:rebill/ub:recharges + /ub:bill/ub:rebill/ub:currentcharges
        totaladjustment = float(self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaladjustment")[0].text)
        balanceforward = float(self.get_elem(tree, "/ub:bill/ub:rebill/ub:balanceforward")[0].text)
        recharges = float(self.get_elem(tree, "/ub:bill/ub:rebill/ub:recharges")[0].text)
        currentcharges = float(self.get_elem(tree, "/ub:bill/ub:rebill/ub:currentcharges")[0].text)

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text = \
            str(totaladjustment + balanceforward + recharges + currentcharges)

        # write bill back out
        xml = etree.tostring(tree, pretty_print=True)
        XMLUtils().save_xml_file(xml, targetBill, user, password)

    def sum_hypothetical_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ Sums up all hypothetical charges.  For each set of hypothetical charges, """
        """ /ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:total = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:charge/ub:total """
        """ For each set of services, /ub:bill/ub:details/ub:total[@type="hypothetical"] = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:total) """
        """ Each /ub:bill/ub:utilbill/ub:hypotheticalecharges = /ub:bill/ub:details/ub:total """
        """ /ub:bill/ub:rebill/ub:hypotheticalecharges = sum(/ub:bill/ub:utilbill/ub:hypotheticalecharges) """

        tree = etree.parse(unprocessedBill)


        # get the child groves for each set of hypothetical charges and total them up
        all_hypothetical_charges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type=\"hypothetical\"]")
        for hypothetical_charges in all_hypothetical_charges:
            # and set the subtotal for for each hypothetical set of charges
            self.get_elem(hypothetical_charges, "ub:total")[0].text = \
            str(self.get_elem(hypothetical_charges, "sum(ub:charge/ub:total)"))

        # for each utility details, sum up the hypothetical charges totals 
        details = self.get_elem(tree, "/ub:bill/ub:details")
        for detail in details:
            total = str(self.get_elem(detail, "sum(ub:chargegroup/ub:charges[@type=\"hypothetical\"]/ub:total)"))
            self.get_elem(detail, "ub:total[@type=\"hypothetical\"]")[0].text = total 
            # now that the utility details are totalized, hypothetical values are put into the utilibill summary
            service_type = detail.attrib["service"]
            self.get_elem(tree, "/ub:bill/ub:utilbill[@service=\""+service_type+"\"]/ub:hypotheticalecharges")[0].text = total
        
        # finally, these hypothetical energy charges get rolled up into rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text = \
        str(self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:hypotheticalecharges)"))

        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, targetBill, user, password)

    def sum_actual_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ Sums up all actual charges.  For each set of actual charges, """
        """ /ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:total = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:charge/ub:total """
        """ For each set of services, /ub:bill/ub:details/ub:total[@type="actual"] = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:total) """
        """ Each /ub:bill/ub:utilbill/ub:actualecharges = /ub:bill/ub:details/ub:total """
        """ /ub:bill/ub:rebill/ub:actualecharges = sum(/ub:bill/ub:utilbill/ub:actualecharges) """

        tree = etree.parse(unprocessedBill)


        # get the child groves for each set of actual charges and total them up
        all_actual_charges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type=\"actual\"]")
        for actual_charges in all_actual_charges:
            # and set the subtotal for for each actual set of charges
            self.get_elem(actual_charges, "ub:total")[0].text = \
            str(self.get_elem(actual_charges, "sum(ub:charge/ub:total)"))

        # for each utility details, sum up the actual charges totals 
        details = self.get_elem(tree, "/ub:bill/ub:details")
        for detail in details:
            total = str(self.get_elem(detail, "sum(ub:chargegroup/ub:charges[@type=\"actual\"]/ub:total)"))
            self.get_elem(detail, "ub:total[@type=\"actual\"]")[0].text = total 
            # now that the utility details are totalized, actual values are put into the utilibill summary
            service_type = detail.attrib["service"]
            self.get_elem(tree, "/ub:bill/ub:utilbill[@service=\""+service_type+"\"]/ub:actualecharges")[0].text = total
        
        # finally, these actual energy charges get rolled up into rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:actualecharges")[0].text = \
        str(self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:actualecharges)"))

        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, targetBill, user, password)



    def roll_bill(self, inputbill, outputbill, amountPaid, user=None, password=None):


        # Bind to XML bill
        tree = etree.parse(inputbill)
        #print etree.tostring(tree, pretty_print=True)

        # increment bill id
        bill = self.get_elem(tree, "/ub:bill")[0]
        newId = int(bill.get("id"))
        bill.set("id", str(newId+1))

        # process /ub:bill/ub:rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaladjustment")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:actualecharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:revalue")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:recharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:resavings")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:currentcharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:duedate")[0].clear()
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:issued")[0].clear()

        message = self.get_elem(tree, "/ub:bill/ub:rebill/ub:message")
        if(len(message)):
            message[0].clear()

        # next period begin is prev period end
        # TODO business logic specific dates are selected here
        # TODO this is an incorrect computation of the re bill period begin - the re bill period begin will be
        # the smallest date of all the utilbill bill period ends
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = \
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].clear()

        # compute payments 
        # TODO if ub:totalDue element does not exist, or has no value, raise exception
        totalDue = self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:priorbalance")[0].text = totalDue
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:paymentreceived")[0].text = str(amountPaid)
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:balanceforward")[0].text = "{0:.2f}".format(float(totalDue) - float(amountPaid))


        # process /ub:bill/ub:utilbill
        utilbills = self.get_elem(tree, "/ub:bill/ub:utilbill")

        # process each utility service and clear values
        for utilbill in utilbills:
            # utility billing periods are utility specific
            # ToDo business logic specific dates are selected here
            self.get_elem(utilbill, "ub:billperiodbegin")[0].text = self.get_elem(utilbill, "ub:billperiodend")[0].text
            self.get_elem(utilbill, "ub:billperiodend")[0].clear()
            self.get_elem(utilbill, "ub:hypotheticalecharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:actualecharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:revalue")[0].text = "0.00"
            self.get_elem(utilbill, "ub:recharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:resavings")[0].text = "0.00"

        # process /ub:bill/ub:details/

        subtotals = self.get_elem(tree, "/ub:bill/ub:details/ub:total")
        for subtotal in subtotals:
            # set text to "" since we don't want to clobber the element attributes
            subtotal.text = "0.00"


        # remove cdata but preserve unit attributes (.clear() clears attrs) -  last period actual charge values 
        actualCharges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type='actual']")
        for actualCharge in actualCharges:
            quantities = self.get_elem(actualCharge, "ub:charge/ub:quantity")
            for quantity in quantities:
                quantity.text = ""
            rates = self.get_elem(actualCharge, "ub:charge/ub:rate")
            for rate in rates:
                rate.text = ""
            totals = self.get_elem(actualCharge, "ub:charge/ub:total")
            for total in totals: 
                total.text = "0.00"
            # clear chargegroup totals
            totals = self.get_elem(actualCharge, "ub:total")
            for total in totals:
                total.text = "0.00"

        # remove the hypothetical charges since they will be recreated from the actual charges
        hypotheticalCharges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type='hypothetical']")

        for hypotheticalCharge in hypotheticalCharges:
            hypotheticalCharge.getparent().remove(hypotheticalCharge)


        # reset measured usage

        # set meter read date
        # ToDo: utility specific behavior
        meters = self.get_elem(tree, "/ub:bill/ub:measuredusage/ub:meter")

        for meter in meters:
            self.get_elem(meter, "ub:priorreaddate")[0].text = self.get_elem(meter, "ub:presentreaddate")[0].text
            self.get_elem(meter, "ub:presentreaddate")[0].clear()

        registerTotals = self.get_elem(tree, "/ub:bill/ub:measuredusage/ub:meter/ub:register/ub:total")
        for registerTotal in registerTotals:
            registerTotal.text = "0"

        
        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, outputbill, user, password)


    def bindrs(self, inputbill, outputbill, rsdb, hypothetical, user=None, password=None):
        """ This function binds a rate structure against the actual and hypothetical charges found """
        """ in a bill. If and RSI specifies information no in the bill, it is added to the bill.   """
        """ If the bill specifies information in a charge that is not in the RSI, the charge is """
        """ left untouched."""
        """ """

        import yaml
        import rate_structure

        # given a bill that has its actual or shadow registers populated, apply a rate structure.

        # load XML bill
        tree = etree.parse(inputbill)


        # TODO: much of the code below to be refactored when register definitions are 
        # placed in the rate structure


        # obtain utilbill groves to determine what services are present
        # identify the per service rate structures for each utilbill
        for utilbill in tree.findall("{bill}utilbill"):

            # get name of the utility
            rsbinding_utilbill = utilbill.get("rsbinding")

            # get service
            service = utilbill.get("service")

            # get name of the rate structure
            # TODO test for one element in array
            rsbinding_rateschedule = self.get_elem(tree, "/ub:bill/ub:details[@service='" + 
                service + "']/ub:rateschedule/@rsbinding")[0]

            # now load the rate structure and configure it
            #rate_structures = yaml.load_all(file(rsdb + os.sep + os.path.join(rsbinding_utilbill, rsbinding_rateschedule) + ".yaml"))
            
            for rs in yaml.load_all(file(rsdb + os.sep 
                + os.path.join(rsbinding_utilbill, rsbinding_rateschedule) + ".yaml")):

                print "*** Loaded Rate Structure for " + service
                print rs
            
            # TODO: only the last rate structure is used.  Use the one that has a valid date
            rs.configure()

            # acquire actual meter registers for this service
            actual_registers = self.get_elem(utilbill, "/ub:bill/ub:measuredusage[@service='" + 
                service + "']/ub:meter/ub:register[@shadow='false']")

            # each service has a number of actual utility registers
            for actual_register in actual_registers:

                # each register has a binding to a register declared in the rate structure
                rsbinding_register = actual_register.get("rsbinding")

                # actual register quantity, with shadow register value optionally added
                register_quantity = 0.0

                # acquire shadow register and track its value
                register_quantity += float(actual_register.find("{bill}total").text)

                if (hypothetical):
                    # acquire shadow register and add its value to the actual register to sum re and ce
                    shadow_reg_total = self.get_elem(actual_register,"../ub:register[@shadow='true' and @rsbinding='"
                        +rsbinding_register+"']/ub:total")[0]
                    register_quantity += float(shadow_reg_total.text)

                # populate rate structure with meter quantities read from XML
                rs.__dict__[rsbinding_register].quantity = register_quantity

            # now that the rate structure is loaded, configured and populated with registers
            # bind to the charge items in the bill

            # if hypothetical, then treat the hypothetical charges. If not, process actual
            charges = None
            if (hypothetical):
                charges = self.get_elem(utilbill, "/ub:bill/ub:details[@service='"
                    + service+"']/ub:chargegroup/ub:charges[@type='hypothetical']/ub:charge")
                # TODO: create the hypothetical charges from the actual charges 
            else:
                charges = self.get_elem(utilbill, "/ub:bill/ub:details[@service='"
                    + service + "']/ub:chargegroup/ub:charges[@type='actual']/ub:charge")
            
            # process each individual charge and bind it to the rate structure
            for charge in charges:
                # a charge may not have a binding because it is not meant to be bound
                charge_binding = charge.get("rsbinding")
                if (charge_binding is None):
                    print "*** No rsbinding for " + etree.tostring(charge)
                    continue

                # obtain the rate structure item that is bound to this charge
                rsi = rs.__dict__[charge_binding]
                # flag the rsi so we can know which RSIs were not processed
                rsi.bound = True

                # if there is a description present in the rate structure, override the value in xml
                # if there is no description in the RSI, leave the one in XML
                if (hasattr(rsi, 'description')):
                    description = charge.find("{bill}description")
                    if (description is None):
                        # description element missing, so insert one
                        description = etree.Element("{bill}description")
                        # description is always first child
                        charge.insert(0, description)
                        print "*** updated charge with description because it was absent in the bill and present in the RSI"
                    description.text = rsi.description

                # if the quantity is present in the rate structure, override value in XML
                if (hasattr(rsi, 'quantity')):
                    quantity = charge.find("{bill}quantity")
                    if (quantity is None):
                        # quantity element is missing, so insert one
                        attribs = {}
                        if (hasattr(rsi, "quantityunits")):
                            attribs["units"] = rsi.quantityunits
                            
                        quantity = etree.Element("{bill}quantity", attribs)
                        # quantity is next sibling of description
                        if (charge.find("{bill}description") is not None):
                            charge.insert(1, quantity)
                        else:
                            charge.insert(0, quantity)
                        print "*** updated charge with quantity because it was absent in the bill and present in the RSI"
                    quantity.text = str(rsi.quantity)

                # if the rate is present in the rate structure, override value in XML
                if (hasattr(rsi, 'rate')):
                    rate = charge.find("{bill}rate")
                    if (rate is None):
                        # rate element missing, so insert one
                        attribs = {}
                        if (hasattr(rsi, "rateunits")):
                            attribs["units"] = rsi.rateunits
                        rate = etree.Element("{bill}rate", attribs)
                        # insert as preceding sibling to the last element which is total
                        total = charge.find("{bill}total")
                        if (total is not None):
                            total.addprevious(rate)
                        else:
                            charge.append(rate)
                        print "*** updated charge with rate because it was absent in the bill and present in the RSI"
                    rate.text = str(rsi.rate)

                total = charge.find("{bill}total")
                if (total is None):
                    # total element is missing, so create one
                    total = etree.Element("{bill}total")
                    # total is always last child
                    charge.append(total)
                    print "*** updated charge with total because it was absent in the bill and present in the RSI"
                total.text = str(rsi.total)

                print etree.tostring(charge)



            for rsi in rs.rates:
                if (hasattr(rsi, 'bound') == False):
                    print "*** RSI was not bound " + str(rsi)

        print "*** Evaluated ratestructure to: " + str(rs)


        XMLUtils().save_xml_file(etree.tostring(tree, pretty_print=True), outputbill, user, password)


def main(options):
    """
    """
    pass

if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-i", "--inputbill", dest="inputbill", help="Previous bill to acted on", metavar="FILE")
    parser.add_option("-o", "--outputbill", dest="outputbill", help="Next bill to be targeted", metavar="FILE")
    parser.add_option("-a", "--amountpaid", dest="amountpaid", help="Amount paid on previous bill")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")
    parser.add_option("--roll", dest="roll", action="store_true", help="Roll the bill to the next period.")
    parser.add_option("--sumhypothetical", action="store_true", dest="sumhypothetical", help="Summarize hypothetical charges.")
    parser.add_option("--sumactual", action="store_true", dest="sumactual", help="Summarize actual charges.")
    parser.add_option("--sumbill", action="store_true", dest="sumbill", help="Calculate total due.")
    parser.add_option("--discountrate",  dest="discountrate", help="Customer energy discount rate from 0.0 to 1.0")
    parser.add_option("--bindrsactual", action="store_true", dest="bindrsactual", help="Bind and evaluate a rate structure.")
    parser.add_option("--bindrshypothetical", action="store_true", dest="bindrshypothetical", help="Bind and evaluate a rate structure.")
    parser.add_option("--rsdb", dest="rsdb", help="Location of the rate structure database.")

    (options, args) = parser.parse_args()

    if (options.inputbill == None):
        print "Input bill must be specified."
        exit()

    if (options.outputbill == None):
        print "Output bill must be specified"
        exit()

    if (options.roll):
        if (options.inputbill == options.outputbill):
            print "Input bill and output bill should not match!"
            exit()
        if (options.amountpaid == None):
            print "Specify --amountpaid"
            exit()
        else:
            BillTool().roll_bill(options.inputbill, options.outputbill, options.amountpaid, options.user, options.password)
            exit()

    if (options.sumhypothetical):
        BillTool().sum_hypothetical_charges(options.inputbill, options.outputbill, options.user, options.password)
        exit()

    if (options.sumactual):
        BillTool().sum_actual_charges(options.inputbill, options.outputbill, options.user, options.password)
        exit()

    if (options.sumbill):
        if (options.discountrate):
            BillTool().sumbill(options.inputbill, options.outputbill, options.discountrate, options.user, options.password)
        else:
            print "Specify --discountrate"
        exit()

    if (options.bindrsactual):
        if (options.rsdb == None):
            print "Specify --rsdb"
            exit()
        BillTool().bindrs(options.inputbill, options.outputbill, options.rsdb, False, options.user, options.password)
        exit()

    if (options.bindrshypothetical):
        if (options.rsdb == None):
            print "Specify --rsdb"
            exit()
        BillTool().bindrs(options.inputbill, options.outputbill, options.rsdb, True, options.user, options.password)
        exit()
        
    print "Specify operation"
