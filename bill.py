#!/usr/bin/python
"""
File: bill.py
Description: Represent pythonically, the bill XML instance
Usage: See command line synopsis
"""
#
# runtime support
#
import sys
import os  
from optparse import OptionParser

from datetime import datetime
from datetime import time
from datetime import date

# for xml processing
from lxml import etree
import lxml
import copy

from skyliner.xml_utils import XMLUtils


# used for processing fixed point monetary decimal numbers
from decimal import *

from collections import namedtuple

from mutable_named_tuple import MutableNamedTuple



# TODO: the xpath functions return a special kind of string. Probably want to convert it before returning int

class Bill(object):
    """
    A container for bill data.  Business logic is purposefully externalized.
    - Return types cannot be JSON encoded because of datetime and decimal types. json_util implements codecs for Date, Time and Decimal.
                # xpath says "all charge children except the sibling total"
    - Returned data are hierarchical MutableNamedTuples, which are OrderedDicts to preserve XML doc order and should be returned as such.
    - This is difficult, because data being posted from a web browser may lose order, therefore the wsgi must pay attention to updating and
     deleting properties in the MutableNamedTuples based on the results in the post.

    XML coding practices/design issues:
    - Tags must be prepended with namespace because {ns} (James Clark notation) is not supported in .xpath()
    - Only use Clark notation for creating elements, if at all
    - Updating the xml document is tricky, this is because updates must delete xml data. How does one know what xml data to delete based on data missing from a passed tuple?
        - One option is to clear the entire grove. This is a poor option, because the grove may contain data that was not originally returned. (see how hypothetical and actual details or how the rebill and utilbill w/ CARs work)
        - The best option appears to be to understand what subset of elements was returned, and then to clear only that subset.  The subset must be determined through parameters that are passed to the getters and setters.  See how get/set details works - charges_type and service specify a subset of elements, which can then be later identified during an update. Also using the function name to convey the subset is useful - e.g. utilbill_summary, excludes the CARs, while utilbill would not.  Each function can the handle deleting and inserting elements accordingly.

    - The DOM is manually manipulated
    - Helper functions for setting properties to and from cdata and attrs are only for terminal leaves of the DOM
    - Optionality of XML elements is left as an exercise for the programmer. In places they are assumed to be mandatory, and already present in the XML document.
    - Document order has to be preserved in the structures returned. Therefore, MutableNamedTuple, a Named Tuple based on an OrderedDict is used.
    - And because there is a document order, the MutableNamedTuple properties need to be initialized so they are slotted in document order.
    - There are two models for returned data:  One where a flat group of element data is needed (e.g. a CAR or summary) and the other where a deep hierarchy is needed (e.g. details or measured usage)
        - Because of this there are two primary patterns: helper function assisted binding to cdata and attrs and walking the tree and manually building nested MutableNamedTuples with helper functions
        - There is no clear generic way to handle both, such a way would be a generic python <-> XML mapper which is too heavy weight.

    Concepts surrounding Bill:
    - bills are selected by account and sequence
    - bills filter their data by service
    - consumers of a Bill have to flatten hierarchical data for wsgi/form posts
    - the only data Bill should act on are data that directly map to and from the underlying XML.  In otherwords, a subtree could be returned from an xpath select, but the resultant structure of that data should not be changed.  For example, flattening chargegroup/charges such that they may be edited in a table.  The consumer of bill does that flattening.

    """
   

    # TODO: don't construct with billref when this container is capable of providing non-xml data to persist
    def __init__(self, billref):
        super(Bill,self).__init__()
        self.inputtree = lxml.etree.parse(billref)

    def xml(self):
        return lxml.etree.tostring(self.inputtree, pretty_print=True)

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    #TODO refactor to external utility class

    def xpath(self, xpath):
        """ Returns all of the results from dereferencing the XPath. """
        return self.inputtree.xpath(xpath, namespaces={"ub":"bill",})

    def remove_children_named(self, root_elem, names):
        for name in names:
            child_elem = root_elem.find("ub:%s" % name, {"ub":"bill"})
            if child_elem is not None:
                root_elem.remove(child_elem)

    def remove_attrs_named(self, elem, names):
        for name in names:
            if name in elem.attrib:
                del elem.attrib[name]


    """
    Notes on the property to xml and xml to property functions.
    First of all, we do not want to be in the business of a generic 
    xml to python mapping (*).  There are too many pitfalls.  Therefore
    an intentional line is drawn between the two way setting of
    python properties (ie those of a tuple) and xml element attributes
    and cdata AND manipulating the xml document structure.
    Consumers of these functions must manipulate the xml document 
    structure and are responsible for conditionally creating
    intermediate nodes whose terminal descendents are then in turn
    individually treated by these functions.
    (*) Why? Ultimately we are only using on XSD so a generic system
    would be wasted and there are other projects that should be 
    considered in the future:
    http://www.rexx.com/~dkuhlman/generateDS.html
    http://www.ibm.com/developerworks/xml/library/x-matters39/index.html
    http://uche.ogbuji.net/tech/4suite/amara/ (sucks and isn't maintained)
    """

    def prop_to_cdata(self, prop_container, prop_name, root_elem, child_elem_name):
        return self.prop_to_cdata_attr(prop_container, prop_name, root_elem, child_elem_name, None)

    def prop_to_cdata_attr(self, prop_container, prop_name, parent_elem, child_elem_name, child_attrs_filter):
        """
        Given a parent_elem that has been cleared of all children (so that doc order
        is implicitly reconstructed), create a new child element of child_elem_name
        if prop_container has an attribute named prop_name. And if so, create cdata
        for the child element if the attribute prop_name has a property value.
        If attrs is passed in, add those attributes to the child element.
        Finer points are:
        There is no good way to track the insertion point for element.insert() so it
        is just easier to have the root element cleared of all children which are then
        added back in the order this function is called.
        """

        # if the property is not present, do nothing as parent_elem has been previously cleared
        if hasattr(prop_container, prop_name):

            # attr exists, so make empty child element if needed

            if child_attrs_filter is not None:
                attributes = ["(@%s='%s')" % (name, value) for name, value in child_attrs_filter]
                attrs_filter = "[" + reduce (lambda reduction, arg: reduction+" and "+arg, attributes) + "]"
                # grr... lxml.find does not support booleans so we use xpath
                child_elem_list = parent_elem.xpath("ub:%s%s" % (child_elem_name, attrs_filter), namespaces={"ub":"bill"})
                child_elem = child_elem_list[0] if child_elem_list else None
            else:
                child_elem = parent_elem.find("ub:%s" % child_elem_name, {"ub":"bill"})
                if child_elem is None:
                    child_elem = parent_elem.makeelement("{bill}%s" % child_elem_name)
                    parent_elem.append(child_elem)

            # add the attributes to the child
            if child_attrs_filter is not None:
                for attr_name, attr_value in child_attrs_filter:
                    child_elem.set(attr_name, attr_value)


            prop_value = prop_container.__getattr__(prop_name)

            if prop_value is not None:

                if type(prop_value) is date:
                    child_elem.text = prop_value.strftime("%Y-%m-%d")
                elif type(prop_value) is time:
                    child_elem.text = prop_value.strftime("%H:%M:%S")
                elif type(prop_value) is str:
                    child_elem.text = prop_value
                elif type(prop_value) is unicode:
                    child_elem.text = prop_value
                elif type(prop_value) is int:
                    child_elem.text = str(prop_value)
                elif type(prop_value) is Decimal:
                    child_elem.text = str(prop_value)
                else:
                    # TODO raise exception
                    pass

            return child_elem

    def attr_to_prop(self, lxml_element, attr_name, prop_type, prop_container, prop_name ):
        """
        Given prop_container set the prop_name attr in the tuple as a prop_type
        whose value is the value of attr_name.
        Finer points:
        Attributes are considered to only be strings. Add a prop_type if that turns out
        to be false
        """
        # if there is no element, then there is no property to be set
        if lxml_element is not None:
            # if there is an attribute, then there is a property to be set
            if attr_name in lxml_element.attrib:
                # set the attribute, though it may still yet be empty
                prop_container.__setattr__(prop_name, None)

                # if there is an attribute value, then there is a property value to be set
                if lxml_element.attrib[attr_name] is not None:
                    if prop_type is bool:
                        if str(lxml_element.attrib[attr_name]).lower() == "true":
                            prop_container.__setattr__(prop_name, True)
                        else:
                            #TODO test for false, and raise error if not
                            prop_container.__setattr__(prop_name, False)
                    elif prop_type is str:
                        prop_container.__setattr__(prop_name, lxml_element.attrib[attr_name])
                    elif prop_type is unicode:
                        prop_container.__setattr__(prop_name, lxml_element.attrib[attr_name])
                    elif prop_type is Decimal:
                        prop_container.__setattr__(prop_name, Decimal(lxml_element.attrib[attr_name]))
                    else:
                        #TODO raise exception
                        pass


    def prop_to_attr(self, prop_container, prop_name, lxml_element, attr_name):
        # TODO: what if there is no element passed in?
        
        # if there is no attribute called  prop_name in prop_container then set no attribute
        if hasattr(prop_container, prop_name):
            prop_value = None
            if type(prop_container.__getattr__(prop_name)) is bool:
                # boolean attributes in bill model are lowercase.
                # TODO: consider making boolean attrs match python str(bool) case which is True v true
                prop_value = str(prop_container.__getattr__(prop_name)).lower()
            else:
                # xml is always string data
                prop_value = str(prop_container.__getattr__(prop_name))

            lxml_element.set(attr_name, prop_value)



    # Done implement this or change xml model for details/total[@type]
    # Done: The problem with this function is that it requires the XSD to not qualify parent_elem with attributes.  
    # What happens when there is one parent with two children with the same tagname yet different attributes?  
    def cdata_to_prop(self, parent_elem, child_elem_name, prop_type, prop_container, prop_name):

        return self.cdata_attr_to_prop(parent_elem, child_elem_name, None, prop_type, prop_container, prop_name)

    # See 13605187 in pivotal
    def cdata_attr_to_prop(self, parent_elem, child_elem_name, child_attrs_filter, prop_type, prop_container, prop_name):
        """
        Given a parent element, a named child element and a filter of attributes used to find the child,
        copy the cdata from the child element into a newly created property of the property container
        Finer points are: 
        If the element does not exist, the property will not exist.
        If the element does exist, the property will exist but be None.
        If the element has cdata, the property will have a value.
        """

        # acquire the child element
        # make attribute filter
        if child_attrs_filter is not None:
            attributes = ["(@%s='%s')" % (name, value) for name, value in child_attrs_filter]
            attrs_filter = "[" + reduce (lambda reduction, arg: reduction+" and "+arg, attributes) + "]"
            # grr... lxml.find does not support booleans so we use xpath
            child_elem_list = parent_elem.xpath("ub:%s%s" % (child_elem_name, attrs_filter), namespaces={"ub":"bill"})
            child_elem = child_elem_list[0] if child_elem_list else None
        else:
            child_elem = parent_elem.find("ub:%s" % child_elem_name, {"ub":"bill"})

        # TODO: ensure that there is only one child named child_elem_name

        if child_elem is None:
            # TODO this may be an exceptional circumstance
            # If there is no child, there is no property
            # print "Could not find child_elem in parent_elem %s child named %s " % (parent_elem.tag, child_elem_name)
            return

        # if there is no element, then there is no property set on prop_container
        if child_elem is not None:

            # if there is an element, set the property but since an element may exist
            # yet have no cdata, set the property to None
            prop_container.__setattr__(prop_name, None)

            # however if the element does have cdata, let's set the property with it
            if child_elem.text is not None:

                # convert child element text to a python string
                cdata = str(child_elem.text)

                # TODO: handle type errors and type formats
                if prop_type is str:
                    prop_container.__setattr__(prop_name, cdata)
                elif prop_type is unicode:
                    prop_container.__setattr__(prop_name, cdata)
                elif prop_type is bool:
                    val = True if cdata.lower() == "true" else False
                    prop_container.__setattr__(prop_name, val)
                elif prop_type is int:
                    prop_container.__setattr__(prop_name, int(cdata))
                elif prop_type is Decimal:
                    prop_container.__setattr__(prop_name, Decimal(cdata))
                elif prop_type is date:
                    prop_container.__setattr__(prop_name, datetime.strptime(cdata, "%Y-%m-%d").date())
                elif prop_type is time:
                    prop_container.__setattr__(prop_name, datetime.strptime(cdata, "%H:%M:%S").time())
                else:
                    # TODO: raise exception
                    # print "Didn't match type"
                    pass
            else:
                pass
                # print "Child has no cdata"

        return prop_container

    @property
    def account(self):
        return self.xpath("/ub:bill/@account")[0]

    # TODO rename to sequnce
    @property
    def id(self):
        return self.xpath("/ub:bill/@id")[0]

    # TODO rename to sequnce
    @id.setter
    def id(self, id):
        self.inputtree.getroot().set("id", str(id))

    @property
    def total_due(self,rounding=None):
        total_due = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        if rounding is None:
            return Decimal(total_due)
        
        return Decimal(total_due).quantize(Decimal(".00"), rounding)

    @property
    def due_date(self):
        r = self.rebill_summary
        return r.duedate

    # TODO convenience method - get issue_date from rebill()
    @property
    def issue_date(self):
        r = self.rebill_summary
        return r.issued
        #return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:issued")[0].text, "%Y-%m-%d").date()


    # return all services
    @property
    def services(self):
        # depend on the utilbill grove to enumerate present services
        # it would then go that to add new services, a utilbill grove must be added
        ub = self.utilbill_summary_charges
        return ub.keys()
        

    @property
    def service_address(self):
        # convenient bulletproof method that returns the desired type. Errors need not be handled.
        #addressee = self.xpath("string(/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee/text())")
        # another way, figure out which is better for the bigger picture. Errors must be handled.
        addressee = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text
        street = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text
        city = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text
        state = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text
        country = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text
        postalcode = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text
        return {"addressee":addressee, "street":street, "city":city, "state":state, "country":country, "postalcode": postalcode}
    
    @service_address.setter
    def service_address(self, service_location):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text = service_location.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text = service_location.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text = service_location.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text = service_location.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text = service_location.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text = service_location.get("postalcode")

    @property
    def billing_address(self):
        # convenient bulletproof method that returns the desired type. Errors need not be handled.
        #addressee = self.xpath("string(/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee/text())")
        # another way, figure out which is better for the bigger picture. Errors must be handled.
        addressee = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee")[0].text
        street = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:street")[0].text
        city = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:city")[0].text
        state = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:state")[0].text
        country = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:country")[0].text
        postalcode = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:postalcode")[0].text
        return {"addressee":addressee, "street":street, "city":city, "state":state, "country":country, "postalcode": postalcode}

    @billing_address.setter
    def billing_address(self, billing_address):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee")[0].text = billing_address.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:street")[0].text = billing_address.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:city")[0].text = billing_address.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:state")[0].text = billing_address.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:country")[0].text = billing_address.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:postalcode")[0].text = billing_address.get("postalcode")

    # convenience method
    # TODO acquire these periods from the function rebill() vs access the xml here
    @property
    def rebill_periods(self):
        begin = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text, "%Y-%m-%d").date()
        end = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text, "%Y-%m-%d").date()
        return {"begin":begin, "end":end}

    @rebill_periods.setter
    # TODO acquire these periods from the function rebill() vs access the xml here
    def rebill_periods(self, periods):
        self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = periods.get("begin").strftime("%Y-%m-%d")
        self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text = periods.get("end").strftime("%Y-%m-%d")


    # TODO call this utilbill, because it is when it returns the cars
    @property
    def utilbill_summary_charges(self):
        """
        Returns a dictionary whose keys are service and values are a MutableNamedTuple excluding the CARs.
        """
        utilbill_elem_list = self.xpath("/ub:bill/ub:utilbill")

        if not utilbill_elem_list: 

            # there are none
            return None

        else:

            utilbill_summary_charges = {}

            for utilbill_elem in utilbill_elem_list:

                u = MutableNamedTuple()

                self.cdata_to_prop(utilbill_elem, "billperiodbegin", date, u, "begin" )
                self.cdata_to_prop(utilbill_elem, "billperiodend", date, u, "end" )
                self.cdata_to_prop(utilbill_elem, "hypotheticalecharges", Decimal, u, "hypotheticalecharges" )
                self.cdata_to_prop(utilbill_elem, "actualecharges", Decimal, u, "actualecharges" )
                self.cdata_to_prop(utilbill_elem, "revalue", Decimal, u, "revalue" )
                self.cdata_to_prop(utilbill_elem, "recharges", Decimal, u, "recharges" )

                # TODO error check absence of attr
                service = utilbill_elem.get("service")
                utilbill_summary_charges[service] = u

            return utilbill_summary_charges

    @utilbill_summary_charges.setter
    def utilbill_summary_charges(self, summary_charges):
        """
        """

        for service, utilbill in summary_charges.items():

            utilbill_elem_list = self.xpath("/ub:bill/ub:utilbill[@service='%s']" % service)

            if not utilbill_elem_list:
                # TODO: there is no utilbill element so let's create it? It is mandatory in xsd..
                pass

            utilbill_elem = utilbill_elem_list[0]

            # clear a subset of terminal elements but preserve the CAR
            self.remove_children_named(utilbill_elem, ["billperiodbegin", "billperiodend", "hypotheticalecharges", "actualecharges",
                "revalue", "recharges", "resavings"])

            self.prop_to_cdata(utilbill, "begin", utilbill_elem, "billperiodbegin")
            self.prop_to_cdata(utilbill, "end", utilbill_elem, "billperiodend")
            self.prop_to_cdata(utilbill, "hypotheticalecharges", utilbill_elem, "hypotheticalecharges")
            self.prop_to_cdata(utilbill, "actualecharges", utilbill_elem, "actualecharges")
            self.prop_to_cdata(utilbill, "revalue", utilbill_elem, "revalue")
            self.prop_to_cdata(utilbill, "recharges", utilbill_elem, "recharges")
            self.prop_to_cdata(utilbill, "resavings", utilbill_elem, "resavings")


    # TODO: pluralize method name
    # TODO: prefix with ub?
    @property
    def measured_usage(self):

        measured_usages = {}

        for service in self.xpath("/ub:bill/ub:measuredusage/@service"):

            measured_usages[service] = []

            #meter_mnt = MutableNamedTuple()

            # a meter
            m = MutableNamedTuple()

            # TODO: do not initialize MNT fields if they do not exist in XML
            #meter_mnt.identifier = None
            #meter_mnt.estimated = None
            #meter_mnt.priorreaddate = None
            #meter_mnt.presentreaddate = None
            # child collections must be initialized
            m.registers = []

            for meter_elem in self.xpath("/ub:bill/ub:measuredusage[@service='"+service+"']/ub:meter"):
                
                self.cdata_to_prop(meter_elem, "identifier", str, m, "identifier" )
                self.cdata_to_prop(meter_elem, "estimated", bool, m, "estimated" )
                self.cdata_to_prop(meter_elem, "priorreaddate", date, m, "priorreaddate" )
                self.cdata_to_prop(meter_elem, "presentreaddate", date, m, "presentreaddate" )

                for register_elem in meter_elem.findall("ub:register", namespaces={'ub':'bill'} ):

                    # a register
                    r = MutableNamedTuple()

                    #TODO: don't initialize these so that they are not returned a artificially set in XML
                    #register_mnt.rsbinding = None
                    #register_mnt.shadow = None
                    #register_mnt.regtype = None
                    #register_mnt.identifier = None
                    #register_mnt.description = None
                    # inclusions/exclusions have been flattened through effective
                    #register_mnt.units = None
                    #register_mnt.total = None
                    #register_mnt.priorreading = None
                    #register_mnt.presentreading = None
                    #register_mnt.factor = None

                    # empty arrays must be initialized
                    r.inclusions = []
                    r.exclusions = []


                    self.attr_to_prop(register_elem, "rsbinding", str, r, "rsbinding")
                    self.attr_to_prop(register_elem, "shadow", bool, r, "shadow")
                    self.attr_to_prop(register_elem, "type", str, r, "type")

                    self.cdata_to_prop(register_elem, "identifier", str, r, "identifier")
                    self.cdata_to_prop(register_elem, "description", str, r, "description")
                    self.cdata_to_prop(register_elem, "units", str, r, "units")
                    self.cdata_to_prop(register_elem, "priorreading", Decimal, r, "priorreading")
                    self.cdata_to_prop(register_elem, "presentreading", Decimal, r, "presentreading")
                    self.cdata_to_prop(register_elem, "factor", Decimal, r, "factor")

                    # TODO optional quantize
                    self.cdata_to_prop(register_elem, "total", Decimal, r, "total")

                    # inclusions are either a Holiday or Days
                    for inclusion_elem in register_elem.findall("ub:effective/ub:inclusions", namespaces={'ub':'bill'}):

                        #TODO figure out what to do with description
                        #description_elem = inclusion_elem.find("ub:description", namespaces={'ub':'bill'})
                        #description = description_elem.text if description_elem is not None else None

                        # either a from/tohour + weekdays is expected or a holiday is expected
                        holiday_elem = inclusion_elem.find("ub:holiday", namespaces={'ub':'bill'})
                        if holiday_elem is not None:

                            # don't initialize properties
                            h = MutableNamedTuple()
                            #holiday_mnt.description = None
                            #holiday_mnt.date = None

                            self.attr_to_prop(holiday_elem, "description", str, h, "description")
                            self.cdata_to_prop(holiday_elem, "date", date, h, "date")

                            r.inclusions.append(h)

                        # then it is a grove of from/tohour w/ weekdays
                        else:

                            # fromhour/tohour + weekday triplets
                            n = MutableNamedTuple()
                            # TODO: don't initialize, doc instead
                            #nonholiday_mnt.fromhour = None
                            #nonholiday_mnt.tohour = None
                            # arrays need to be initialized
                            n.weekdays = []
    
                            self.cdata_to_prop(inclusion_elem, "fromhour", time, n, "fromhour")
                            self.cdata_to_prop(inclusion_elem, "tohour", time, n, "tohour")
                            for child_elem in inclusion_elem.iterchildren():
                                # occurs multiple times
                                if (child_elem.tag == "{bill}weekday"):
                                    # adjacent weekday tags breaks the cdata_to_prop model
                                    weekday = child_elem.text if child_elem.text is not None else None
                                    if weekday is not None:
                                        n.weekdays.append(weekday)

                            r.inclusions.append(n)

                    # TODO refactor so that inclusions AND exclusions are treated in the same block of code. (See above)
                    # exclusions are either a Holiday or Days
                    for exclusion_elem in register_elem.findall("ub:effective/ub:exclusions", namespaces={'ub':'bill'}):

                        # figure out what to do with description
                        #description_elem = exclusion_elem.find("ub:description", namespaces={'ub':'bill'})
                        #description = description_elem.text if description_elem is not None else None

                        # either a from/tohour + weekdays is expected or a holiday is expected
                        holiday_elem = exclusion_elem.find("ub:holiday", namespaces={'ub':'bill'})
                        if holiday_elem is not None:

                            h = MutableNamedTuple()
                            #holiday_mnt.description = None
                            #holiday_mnt.date = None

                            self.attr_to_prop(holiday_elem, "description", str, h, "description")
                            self.cdata_to_prop(holiday_elem, "date", date, h, "date")

                            r.exclusions.append(h)

                        # then it is a grove of from/tohour w/ weekdays
                        else:

                            # fromhour/tohour + weekday triplets
                            n = MutableNamedTuple()
                            #nonholiday_mnt.fromhour = None
                            #nonholiday_mnt.tohour = None
                            n.weekdays = []

                            self.cdata_to_prop(exclusion_elem, "fromhour", time, n, "fromhour")
                            self.cdata_to_prop(exclusion_elem, "tohour", time, n, "tohour")
                            for child_elem in exclusion_elem.iterchildren():
                                # occurs multiple times
                                if (child_elem.tag == "{bill}weekday"):
                                    weekday = child_elem.text if child_elem.text is not None else None

                                    if weekday is not None:
                                        n.weekdays.append(weekday)

                            r.exclusions.append(n)

                    m.registers.append(r)

                measured_usages[service].append(m)

        return measured_usages


    # convert to helper functions
    @measured_usage.setter
    def measured_usage(self, measured_usage):

        for service, meters in measured_usage.items():

            measuredusage_elem = self.xpath("/ub:bill/ub:measuredusage[@service='%s']" % service)[0]
            measuredusage_elem.clear()
            measuredusage_elem.set('service', service)

            for meter in meters:
                
                meter_elem = measuredusage_elem.makeelement("{bill}meter")
                measuredusage_elem.append(meter_elem)

                self.prop_to_cdata(meter, "identifier", meter_elem, "identifier")
                self.prop_to_cdata(meter, "identifier", meter_elem, "identifier")
                self.prop_to_cdata(meter, "priorreaddate", meter_elem, "priorreaddate")
                self.prop_to_cdata(meter, "presentreaddate", meter_elem, "presentreaddate")

                for register in meter.registers:

                    register_elem = meter_elem.makeelement("{bill}register")
                    meter_elem.append(register_elem)

                    self.prop_to_attr(register, "rsbinding", register_elem, "rsbinding")
                    self.prop_to_attr(register, "shadow", register_elem, "shadow")
                    self.prop_to_attr(register, "type", register_elem, "type")
                    self.prop_to_cdata(register, "identifier", register_elem, "identifier")
                    self.prop_to_cdata(register, "description", register_elem, "description")

                    # inclusions/exclusions had been flattened through effective
                    effective_elem = register_elem.makeelement("{bill}effective")
                    register_elem.append(effective_elem)

                    self.prop_to_cdata(register, "units", register_elem, "units")
                    self.prop_to_cdata(register, "total", register_elem, "total")
                    self.prop_to_cdata(register, "priorreading", register_elem, "priorreading")
                    self.prop_to_cdata(register, "presentreading", register_elem, "presentreading")
                    self.prop_to_cdata(register, "factor", register_elem, "factor")

                    for inclusion in register.inclusions:

                        inclusion_elem = effective_elem.makeelement("{bill}inclusions")
                        effective_elem.append(inclusion_elem)

                        # determine if a from/tohour triplet or holiday
                        if (hasattr(inclusion, "fromhour")):

                            self.prop_to_cdata(inclusion, "fromhour", inclusion_elem, "fromhour")

                            self.prop_to_cdata(inclusion, "tohour", inclusion_elem, "tohour")

                            for weekday in inclusion.weekdays:
                                # TODO: support directly setting cdata
                                #self.prop_to_cdata(None, weekday, inclusion_elem, "weekday")
                                weekday_elem = inclusion_elem.makeelement("{bill}weekday")
                                weekday_elem.text = weekday
                                inclusion_elem.append(weekday_elem)

                        # holiday
                        else:
                            self.prop_to_attr(inclusion, "description", inclusion_elem, "description")
                            self.prop_to_cdata(inclusion, "holiday", inclusion_elem, "holiday")

                    for exclusion in register.exclusions:

                        exclusion_elem = effective_elem.makeelement("{bill}exclusions")
                        effective_elem.append(exclusions_elem)

                        # determine if a from/tohour triplet or holiday
                        if (hasattr(exclusion, "fromhour")):

                            self.prop_to_cdata(exclusion, "fromhour", exclusion_elem, "fromhour")

                            self.prop_to_cdata(exclusion, "tohour", exclusion_elem, "tohour")

                            for weekday in exclusion.weekdays:
                                # TODO: support directly setting cdata
                                #self.prop_to_cdata(None, weekday, exclusion_elem, "weekday")
                                weekday_elem = exclusion_elem.makeelement("{bill}weekday")
                                weekday_elem.text = weekday
                                exclusion_elem.append(weekday_elem)

                        # holiday
                        else:
                            self.prop_to_attr(exclusion, "description", exclusion_elem, "description")
                            self.prop_to_cdata(exclusion, "holiday", exclusion_elem, "holiday")

                #print lxml.etree.tostring(measuredusage_elem, pretty_print=True)
                #print lxml.etree.tostring(self.inputtree, pretty_print=True)

    # TODO rename to rebill, and send entire grove
    @property
    def rebill_summary(self):

        rebill_elem_list = self.xpath("/ub:bill/ub:rebill")

        if not rebill_elem_list: 

            # there is no rebill element
            return None

        else:
            rebill_elem = rebill_elem_list[0]

            r = MutableNamedTuple()

            # TODO: pass in root element, and lookup subelement
            self.cdata_to_prop(rebill_elem, "billperiodbegin", date, r, "begin" )
            self.cdata_to_prop(rebill_elem, "billperiodend", date, r, "end")
            self.cdata_to_prop(rebill_elem, "priorbalance", Decimal, r, "priorbalance" )
            self.cdata_to_prop(rebill_elem, "paymentreceived", Decimal, r, "paymentreceived")
            self.cdata_to_prop(rebill_elem, "totaladjustment", Decimal, r, "totaladjustment")
            self.cdata_to_prop(rebill_elem, "balanceforward", Decimal, r, "balanceforward")
            self.cdata_to_prop(rebill_elem, "hypotheticalecharges", Decimal, r, "hypotheticalecharges")
            self.cdata_to_prop(rebill_elem, "actualecharges", Decimal, r, "actualecharges")
            self.cdata_to_prop(rebill_elem, "revalue", Decimal, r, "revalue")
            self.cdata_to_prop(rebill_elem, "resavings", Decimal, r, "resavings")
            self.cdata_to_prop(rebill_elem, "recharges", Decimal, r, "recharges")
            self.cdata_to_prop(rebill_elem, "totaldue", Decimal, r, "totaldue")
            self.cdata_to_prop(rebill_elem, "duedate", date, r, "duedate")
            self.cdata_to_prop(rebill_elem, "issued", date, r, "issued")
            self.cdata_to_prop(rebill_elem, "message", str, r, "message")

            return r


    @rebill_summary.setter
    def rebill_summary(self, r):

        rebill_elem_list = self.xpath("/ub:bill/ub:rebill")

        if not rebill_elem_list:
            # TODO: there is no rebill element so let's create it
            pass

        rebill_elem = rebill_elem_list[0]

        # clear the entire grove, because present properties have to be added back in
        # document order.  It would be difficult to delete/create each child because
        # the insertion location would have to be tracked here.
        # crap.. just can't clear because of sibling groves, list the car
        #rebill_elem.clear()
        self.remove_children_named(rebill_elem, ["billperiodbegin", "billperiodend", "priorbalance", "paymentreceived",
            "totaladjustment", "balanceforward", "hypotheticalecharges", "actualecharges", "revalue", "resavings", 
            "currentcharges", "recharges", "totaldue", "duedate", "issued", "message"])


        self.prop_to_cdata(r, "begin", rebill_elem, "billperiodbegin")
        self.prop_to_cdata(r, "end", rebill_elem, "billperiodend")
        self.prop_to_cdata(r, "priorbalance", rebill_elem, "priorbalance")
        self.prop_to_cdata(r, "paymentreceived", rebill_elem, "paymentreceived")
        self.prop_to_cdata(r, "totaladjustment", rebill_elem, "totaladjustment")
        self.prop_to_cdata(r, "balanceforward", rebill_elem, "balanceforward")
        self.prop_to_cdata(r, "hypotheticalecharges", rebill_elem, "hypotheticalecharges")
        self.prop_to_cdata(r, "actualecharges", rebill_elem, "actualecharges")
        self.prop_to_cdata(r, "revalue", rebill_elem, "revalue")
        self.prop_to_cdata(r, "recharges", rebill_elem, "recharges")
        self.prop_to_cdata(r, "resavings", rebill_elem, "resavings")
        self.prop_to_cdata(r, "currentcharges", rebill_elem, "currentcharges")
        self.prop_to_cdata(r, "totaldue", rebill_elem, "totaldue")
        self.prop_to_cdata(r, "duedate", rebill_elem, "duedate")
        self.prop_to_cdata(r, "issued", rebill_elem, "issued")
        self.prop_to_cdata(r, "message", rebill_elem, "message")


    @property
    def actual_details(self):
        """
        Return by service, actual charges grouped by chargegroup including chargegroup totals.
        """
        return self.details('actual')

    @property
    def hypothetical_details(self):
        """
        Return by service, actual charges grouped by chargegroup including chargegroup totals.
        """
        return self.details('hypothetical')

    @actual_details.setter
    def actual_details(self, details):
        return self.set_details('actual', details)

    @hypothetical_details.setter
    def hypothetical_details(self, details):
        return self.set_details('hypothetical', details)

    @property
    def actual_charges(self):
        """
        Return by service, actual charges grouped by chargegroup including chargegroup totals.
        """
        return self.charge_items('actual')

    # TODO: this can depend on set_details
    @actual_charges.setter
    def actual_charges(self, charge_items):
        """
        Set the actual charges into XML
        """
        return self.set_charge_items('actual', charge_items)

    # TODO: this can depend on set_details
    @property
    def hypothetical_charges(self):
        """
        Return by service, hypothetical charges grouped by chargegroup including chargegroup totals.
        """
        return self.charge_items('hypothetical')

    # TODO: this can depend on set_details
    @hypothetical_charges.setter
    def hypothetical_charges(self, charge_items):
        """
        Set the hypothetical charges into XML
        """
        return self.set_charge_items('hypothetical', charge_items)


    # consider merging the charge_items code in here
    def details(self, charges_type):
        """
        Return details by service
        """

        details = {} 

        # enumerate each detail by service
        for detail in self.xpath("/ub:bill/ub:details"):

            service = detail.get("service")

            # handle detail parent
            # TODO: doc up finer points about this tuple
            # Properties have to be initialized in document order
            # Properties cannot be pre-initialized because they may not exist
            # Properties that are container types (like chargegroups below) should
            # not be initialized until they are going to be used.
            detail_mnt = MutableNamedTuple()
            #detail_mnt.rateschedule = None
            # TODO: we don't want to have to initialize the mnt's because the properties may not exist
            # so initialize the array if there are chargegroups.
            #detail_mnt.chargegroups = []
            #detail_mnt.total = None

            # handle rateschedule child grove
            rateschedule_elem = detail.find("ub:rateschedule", {"ub":"bill"})

            rateschedule_mnt = MutableNamedTuple()
            #rateschedule_mnt.rsbinding = None
            #rateschedule_mnt.name = None

            self.cdata_to_prop(rateschedule_elem, "name", str, rateschedule_mnt, "name")
            self.attr_to_prop(rateschedule_elem, "rsbinding", str, rateschedule_mnt, "rsbinding")

            detail_mnt.rateschedule = rateschedule_mnt

            for chargegroup in detail.findall("ub:chargegroup", {"ub":"bill"}):

                chargegroup_mnt = MutableNamedTuple()

                self.attr_to_prop(chargegroup, "type", str, chargegroup_mnt, "type")

                # there are only two types of charges per chargegroup
                for charges_child in chargegroup.find("ub:charges[@type='%s']" % (charges_type), {"ub":"bill"}):

                    if charges_child.tag == "{bill}charge":

                        charge_mnt = MutableNamedTuple()
                        # For illustrating the tuple properties, but do not set them so function below can do so as a function of the XML
                        #charge_mnt.rsbinding = None
                        #charge_mnt.description = None
                        #charge_mnt.quantity = None
                        #charge_mnt.quantityunits = None
                        #charge_mnt.rate = None
                        #charge_mnt.rateunits = None
                        #charge_mnt.total = None
                        #charge_mnt.processingnote = None

                        self.attr_to_prop(charges_child, "rsbinding", str, charge_mnt, "rsbinding")
                        self.cdata_to_prop(charges_child, "description", str, charge_mnt, "description")
                        self.cdata_to_prop(charges_child, "quantity", Decimal, charge_mnt, "quantity")
                        self.attr_to_prop(charges_child.find("ub:quantity", {"ub":"bill"}), "units", str, charge_mnt, "quantityunits")
                        self.cdata_to_prop(charges_child, "rate", Decimal, charge_mnt, "rate")
                        self.attr_to_prop(charges_child.find("ub:rate", {"ub":"bill"}), "units", str, charge_mnt, "rateunits")
                        self.cdata_to_prop(charges_child, "total", Decimal, charge_mnt, "total")
                        self.cdata_to_prop(charges_child, "processingnote", str, charge_mnt, "processingnote")

                        # initialize the charges property as an array if it has not already been done
                        if not hasattr(chargegroup_mnt, "charges"): chargegroup_mnt.charges = []
                        chargegroup_mnt.charges.append(charge_mnt)

                    elif charges_child.tag == "{bill}total":

                        total_mnt = MutableNamedTuple()

                        # total is a sibling to the charges that are being iterated
                        # therefore, when a total is encountered, have to go up a level for cdata_to_prop
                        self.cdata_to_prop(charges_child.getparent(), "total", Decimal, total_mnt, "total")


                        # TODO: why append total to the charges list? Why not chargegroup_mnt.charges.total? Would that simplify the set_details code?
                        # because mnt's don't nest unless another mnt is initialized, and the total is a sibling to the charges, so why deviate from
                        # the xml model?
                        chargegroup_mnt.charges.append(total_mnt)


                # initialize the chargegroups property as an array if it has not already been done
                if not hasattr(detail_mnt, "chargegroups"): detail_mnt.chargegroups = []
                detail_mnt.chargegroups.append(chargegroup_mnt)

            self.cdata_attr_to_prop(detail, "total", [("type", charges_type)], Decimal, detail_mnt, "total")

            details[service] = detail_mnt

        return details 

    def set_details(self, charges_type, details):
        """
        details
        """

        for service, details in details.items():
            """
            The trick here is that actual and hypothetical charges live side-by-side
            so we have to insert the charges_type in their proper xml locations.
            """

            # TODO error check this
            details_elem = self.xpath("/ub:bill/ub:details[@service='%s']" % service)[0]

            # handle rate schedule
            # rateschedule is global to actual and hypothetical so create it if necessary

            rateschedule_elem = details_elem.find("ub:rateschedule", {"ub":"bill"})
            if rateschedule_elem is None:
                rateschedule_elem = details_elem.makeelement("{bill}rateschedule")
                # a rate schedule is always the first child
                detail_elem.insert(0, rateschedule_elem)

            # attrs and children are mandatory elements
            #self.remove_attrs_named(rateschedule_elem, ["rsbinding"])
            #self.remove_children_named(rateschedule_elem, ["name"])

            self.prop_to_attr(details, "rsbinding", rateschedule_elem, "rsbinding")
            self.prop_to_cdata(details.rateschedule, "name", rateschedule_elem, "name")

            # handle chargegroups
            for chargegroup in details.chargegroups:

                # clear out all chargegroups from xml so that deletions occur
                #[details_elem.remove(elem) for elem in details_elem.findall("ub:chargegroup", {"ub":"bill"})

                #print chargegroup.type

                # identify the chargegroup in question or create it
                chargegroup_elem = details_elem.find("ub:chargegroup[@type='%s']" % chargegroup.type, {"ub":"bill"})

                if chargegroup_elem is None:
                    # append new chargegroup to end of list of chargegroups
                    chargegroup_elem = details_elem.makeelement("{bill}chargegroup")

                self.prop_to_attr(chargegroup, "type", chargegroup_elem, "type")

                # handle charges of charges_type
                # identify charges element
                charges_elem = chargegroup_elem.find("ub:charges[@type='%s']" % charges_type)
                if charges_elem is None:
                    charges_elem = chargegroup_elem.makeelement("{bill}charges")
                    # don't worry about insertion point because the order does not matter
                    chargegroup_elem.append(charges_elem)
                else:
                    # clear all child charge elements of charges
                    charges_elem.clear()

                # set attribute back since clear wipes it
                charges_elem.set("type", charges_type)

                # all charges except for the last which is the total
                for charge in chargegroup.charges[:-1]:
                    charge_elem = charges_elem.makeelement("{bill}charge")

                    self.prop_to_attr(charge, "rsbinding", charge_elem, "rsbinding")
                    self.prop_to_cdata(charge, "description", charge_elem, "description")
                    self.prop_to_cdata(charge, "quantity", charge_elem, "quantity")
                    # TODO check to see if quantity exists first
                    self.prop_to_attr(charge, "quantityunits", charge_elem.find("ub:quantity", {"ub":"bill"}), "units")
                    self.prop_to_cdata(charge, "rate", charge_elem, "rate")
                    # TODO check to see if rate exists first
                    self.prop_to_attr(charge, "rateunits", charge_elem.find("ub:rate", {"ub":"bill"}), "units")
                    self.prop_to_cdata(charge, "total", charge_elem, "total")
                    self.prop_to_cdata(charge, "processingnote", charge_elem, "processingnote")

                    charges_elem.append(charge_elem)

                # the last element, the total for all the charges
                total = chargegroup.charges[-1]
                self.prop_to_cdata(total, "total", charges_elem, "total")

            # TODO: prune remaining empty chargegroups

            # TODO: chargegroup totals

            # handle total of charges_type
            # assumes type=charges_type is a mandatory element since attr is not set
            # this won't work because details_elem is qualified by the attribute 'type' whose value is charges_type
            # unfortunately, there are to child elements called total due to the hypothetical and actual charges living side by side
            self.prop_to_cdata_attr(details, "total", details_elem, "total", [("type", charges_type)])


    # until the XML model is changed to remove the charge sibling total to another location
    # UI code needs this support because it is not possible to distinguish the types of tuples in an array. <charge/><total/> becomes [tuple, tuple]
    # so, we return only charges.  details() will be used in the future when the consumer of details can look only at charges and not have to worry about totals.
    @property
    def actual_charges_no_totals(self):
        return self.charge_items_no_totals('actual')

    @property
    def hypothetical_charges_no_totals(self):
        return self.charge_items_no_totals('hypothetical')

    def charge_items_no_totals(self, charges_type):
        """
        """
        # a dictionary of chargegroups whose key is service
        charge_items = {} 

        # enumerate each detail by service
        for detail in self.xpath("/ub:bill/ub:details"):

            service = detail.get("service")

            charge_items[service] = MutableNamedTuple()

            charge_items[service].chargegroups = []

            for chargegroup in detail.findall("ub:chargegroup", {"ub":"bill"}):

                chargegroup_mnt = MutableNamedTuple()

                self.attr_to_prop(chargegroup, "type", str, chargegroup_mnt, "type")

                for charges_child in chargegroup.find("ub:charges[@type='%s']" % (charges_type), {"ub":"bill"}):

                    if charges_child.tag == "{bill}charge":

                        charge_mnt = MutableNamedTuple()

                        self.attr_to_prop(charges_child, "rsbinding", str, charge_mnt, "rsbinding")
                        self.cdata_to_prop(charges_child, "description", str, charge_mnt, "description")
                        self.cdata_to_prop(charges_child, "quantity", Decimal, charge_mnt, "quantity")
                        self.attr_to_prop(charges_child.find("ub:quantity", {"ub":"bill"}), "units", str, charge_mnt, "quantityunits")
                        self.cdata_to_prop(charges_child, "rate", Decimal, charge_mnt, "rate")
                        self.attr_to_prop(charges_child.find("ub:rate", {"ub":"bill"}), "units", str, charge_mnt, "rateunits")
                        self.cdata_to_prop(charges_child, "total", Decimal, charge_mnt, "total")
                        self.cdata_to_prop(charges_child, "processingnote", str, charge_mnt, "processingnote")

                        # initialize the charges property as an array if it has not already been done
                        if not hasattr(chargegroup_mnt, "charges"): chargegroup_mnt.charges = []
                        chargegroup_mnt.charges.append(charge_mnt)

                    elif charges_child.tag == "{bill}total":
                        pass

                charge_items[service].chargegroups.append(chargegroup_mnt)

        return charge_items 

    def charge_items(self, charges_type):
        """
        """

        # a dictionary with service as keys
        charge_items = {} 

        # enumerate each detail by service
        for detail in self.xpath("/ub:bill/ub:details"):

            service = detail.get("service")

            charge_items[service] = MutableNamedTuple()

            self.cdata_attr_to_prop(detail, "total", [("type", charges_type)], Decimal, charge_items[service], "total")

            charge_items[service].chargegroups = []

            for chargegroup in detail.findall("ub:chargegroup", {"ub":"bill"}):

                chargegroup_mnt = MutableNamedTuple()

                self.attr_to_prop(chargegroup, "type", str, chargegroup_mnt, "type")
                # eventually chargegroups should have totals too
                #self.cdata_to_prop(chargegroup, "total", Decimal, chargegroup_mnt, "total")


                for charges_child in chargegroup.find("ub:charges[@type='%s']" % (charges_type), {"ub":"bill"}):

                    # initialize the charges property as an array if it has not already been done
                    if not hasattr(chargegroup_mnt, "charges"): chargegroup_mnt.charges = []

                    if charges_child.tag == "{bill}charge":

                        charge_mnt = MutableNamedTuple()

                        self.attr_to_prop(charges_child, "rsbinding", str, charge_mnt, "rsbinding")
                        self.cdata_to_prop(charges_child, "description", str, charge_mnt, "description")
                        self.cdata_to_prop(charges_child, "quantity", Decimal, charge_mnt, "quantity")
                        self.attr_to_prop(charges_child.find("ub:quantity", {"ub":"bill"}), "units", str, charge_mnt, "quantityunits")
                        self.cdata_to_prop(charges_child, "rate", Decimal, charge_mnt, "rate")
                        self.attr_to_prop(charges_child.find("ub:rate", {"ub":"bill"}), "units", str, charge_mnt, "rateunits")
                        self.cdata_to_prop(charges_child, "total", Decimal, charge_mnt, "total")
                        self.cdata_to_prop(charges_child, "processingnote", str, charge_mnt, "processingnote")

                        chargegroup_mnt.charges.append(charge_mnt)

                    elif charges_child.tag == "{bill}total":

                        total_mnt = MutableNamedTuple()

                        self.cdata_to_prop(charges_child.getparent(), "total", Decimal, total_mnt, "total")

                        # TODO: why append total to the charges list? Why not chargegroup_mnt.charges.total? Would that simplify the set_details code?
                        # because mnt's don't nest unless another mnt is initialized, and the total is a sibling to the charges, so why deviate from
                        # the xml model?
                        chargegroup_mnt.charges.append(total_mnt)

                charge_items[service].chargegroups.append(chargegroup_mnt)

        return charge_items 


    """
        old version
        Return ci_type charge items by service with charges grouped by chargegroup including chargegroup and grand totals.
        charge_items = {} 

        # this is really pedantic, but incrementally building the xpath makes the code much clearer

        # get each type of service present
        for detail_service in self.xpath("/ub:bill/ub:details/@service"):

            # convert lxml object to a string to act as dict key
            detail_service = str(detail_service)
            
            charge_items[detail_service] = {}
            
            grand_total = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (detail_service, charges_type))[0].text

            charge_items[detail_service]['chargegroups'] = {}
            charge_items[detail_service]['total'] = Decimal(grand_total)
            #.quantize(Decimal('.0000'))

            # get chargegroup types for that service
            for cg_type in self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup/@type" % detail_service):

                # convert lxml object to a string to act as dict key
                cg_type = str(cg_type)

                charge_items[detail_service]['chargegroups'][cg_type] = {}

                # get the charges of charges_type from the chargegroup
                for charges in self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup[@type='%s']/ub:charges[@type='%s']" % (detail_service, cg_type, charges_type)):

                    charge_items[detail_service]['chargegroups'][cg_type]['charges'] = []

                    charge_items[detail_service]['chargegroups'][cg_type]['total'] = Decimal(charges.find("ub:total", namespaces={"ub":"bill"}).text)
                    #.quantize(Decimal('.0000'))
                    
                    for charge in charges.findall("ub:charge", namespaces={"ub":"bill"}):

                        rsbinding = charge.get('rsbinding')

                        description = charge.find("ub:description", namespaces={'ub':'bill'})
                        description = description.text if description is not None else None

                        quantity = charge.find("ub:quantity", namespaces={'ub':'bill'})
                        quantity = quantity.text if quantity is not None else None

                        # TODO review lxml api for a better method to access attributes
                        quantity_units = charge.xpath("ub:quantity/@units", namespaces={'ub':'bill'})
                        if (len(quantity_units)):
                            quantity_units = quantity_units[0]
                        else:
                            quantity_units = ""

                        # TODO helper to quantize based on units
                        # TODO not sure we want to quantize here. think it over.
                        if (quantity_units.lower() == 'therms'):
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'dollars'):
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'kwh'):
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.0'))

                        rate = charge.find("ub:rate", namespaces={'ub':'bill'})
                        rate = rate.text if rate is not None else None
                        
                        # TODO review lxml api for a better method to access attributes
                        rate_units = charge.xpath("ub:rate/@units", namespaces={'ub':'bill'})
                        if (len(rate_units)):
                            rate_units = rate_units[0]
                        else:
                            rate_units = ""

                        total = charge.find("ub:total", namespaces={'ub':'bill'})
                        total = Decimal(total.text) if total is not None else None
                        #.quantize(Decimal('.0000'))

                        processingnote = charge.find("ub:processingnote", namespaces={'ub':'bill'})
                        processingnote = processingnote.text if processingnote is not None else None

                        charge_items[detail_service]['chargegroups'][cg_type]['charges'].append({
                            'rsbinding': rsbinding,
                            'description': description,
                            'quantity': quantity,
                            'quantity_units': quantity_units,
                            'rate': rate,
                            'rate_units': rate_units,
                            'total': total,
                            'processingnote': processingnote
                        })

        return charge_items
    """

    # TODO convert to helper methods
    def set_charge_items_old(self, charges_type, charge_items):

        # get each service name, and associated chargegroups
        for service in charge_items:
            # TODO: create the service in XML if it does not exist
            for chargegroup in charge_items[service]['chargegroups']:
                # TODO: create the chargeroup in XML if it does not exist

                # lookup the charge_type (hypothetical or actual) charges in the chargegroup
                charges_elem = self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup[@type='%s']/ub:charges[@type='%s']" % (service, chargegroup, charges_type))[0]

                # remove all charges_type children
                charges_elem.clear()
                # add the attr back since clear clears everything
                charges_elem.set('type', charges_type)

                for charge in charge_items[service]['chargegroups'][chargegroup]['charges']:
                    rsbinding = charge['rsbinding']
                    description = charge['description']
                    rate = charge['rate']
                    rate_units = charge['rate_units']
                    quantity = charge['quantity']
                    quantity_units = charge['quantity_units']
                    total = charge['total']
                    processingnote = charge['processingnote'] if 'processingnote' in charge else None

                    # append new charge to charges
                    charge_elem = charges_elem.makeelement("{bill}charge", rsbinding=rsbinding if rsbinding is not None else "")
                    charges_elem.append(charge_elem)

                    # append new description to charge
                    description_elem = charge_elem.makeelement("{bill}description")
                    description_elem.text = description
                    charge_elem.append(description_elem)

                    # append new quantity and units to charge
                    quantity_elem = charge_elem.makeelement("{bill}quantity")
                    quantity_elem.text = str(quantity)
                    quantity_elem.set('units', quantity_units)
                    charge_elem.append(quantity_elem)

                    # append new rate units to charge
                    rate_elem = charge_elem.makeelement("{bill}rate")
                    rate_elem.text = str(rate)
                    rate_elem.set('units', rate_units)
                    charge_elem.append(rate_elem)

                    # append new total to charge
                    total_elem = charge_elem.makeelement("{bill}total")
                    total_elem.text = str(total)
                    charge_elem.append(total_elem)

                    # append new processing notes to charge
                    note_elem = charge_elem.makeelement("{bill}processingnote")
                    note_elem.text = processingnote
                    charge_elem.append(note_elem)

                charges_total = charge_items[service]['chargegroups'][chargegroup]['total']

                charges_total_elem = charges_elem.makeelement("{bill}total")
                charges_total_elem.text = str(charges_total)
                charges_elem.append(charges_total_elem)

            grand_total = charge_items[service]['total']

            # TODO and the details total should by dynamically created too
            grand_total_elem = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (service, charges_type))[0]
            grand_total_elem.text = str(grand_total)


    # set_details could depend on this code

    def set_charge_items(self, charges_type, charge_items):


        for service, detail_charge_items in charge_items.items():
            """
            The trick here is that actual and hypothetical charges live side-by-side
            so we have to insert the charges_type in their proper xml locations.
            """

            # TODO error check this
            details_elem = self.xpath("/ub:bill/ub:details[@service='%s']" % service)[0]
            # handle chargegroups
            for chargegroup in detail_charge_items.chargegroups:

                # identify the chargegroup in question or create it
                chargegroup_elem = details_elem.find("ub:chargegroup[@type='%s']" % chargegroup.type, {"ub":"bill"})

                if chargegroup_elem is None:
                    # append new chargegroup to end of list of chargegroups
                    chargegroup_elem = details_elem.makeelement("{bill}chargegroup")

                self.prop_to_attr(chargegroup, "type", chargegroup_elem, "type")

                # handle charges of charges_type
                # identify charges element
                charges_elem = chargegroup_elem.find("ub:charges[@type='%s']" % charges_type, {"ub":"bill"})
                if charges_elem is None:
                    charges_elem = chargegroup_elem.makeelement("{bill}charges")
                    # don't worry about insertion point because the order does not matter
                    chargegroup_elem.append(charges_elem)
                else:
                    # clear all child charge elements of charges
                    charges_elem.clear()

                # set attribute back since clear wipes it
                charges_elem.set("type", charges_type)

                # all charges except for the last which is the total
                # enumerate so we can track index and detect presence/absence of total tuple
                # TODO gotta fix the charge/total sibling issue
                for index, charge in enumerate(chargegroup.charges):
                    if index == len(chargegroup.charges)-1 and len(charge) == 1 and charge.keys()[0] == "total":
                        # the last element, the total for all the charges
                        total = charge
                        self.prop_to_cdata(total, "total", charges_elem, "total")
                    else:

                        charge_elem = charges_elem.makeelement("{bill}charge")

                        self.prop_to_attr(charge, "rsbinding", charge_elem, "rsbinding")
                        self.prop_to_cdata(charge, "description", charge_elem, "description")
                        self.prop_to_cdata(charge, "quantity", charge_elem, "quantity")
                        # TODO check to see if quantity exists first
                        self.prop_to_attr(charge, "quantityunits", charge_elem.find("ub:quantity", {"ub":"bill"}), "units")
                        self.prop_to_cdata(charge, "rate", charge_elem, "rate")
                        # TODO check to see if rate exists first
                        self.prop_to_attr(charge, "rateunits", charge_elem.find("ub:rate", {"ub":"bill"}), "units")
                        self.prop_to_cdata(charge, "total", charge_elem, "total")
                        self.prop_to_cdata(charge, "processingnote", charge_elem, "processingnote")

                        charges_elem.append(charge_elem)

                # TODO gotta fix the charge/total sibling issue
                if index == len(chargegroup.charges)-1 and len(charge) != 1 and charge.keys()[0] != "total":
                    total = MutableNamedTuple([("total", "0.00")])
                    self.prop_to_cdata(total, "total", charges_elem, "total")



            # TODO: prune remaining empty chargegroups

            # TODO: chargegroup totals

            # handle total of charges_type
            # assumes type=charges_type is a mandatory element since attr is not set
            # this won't work because details_elem is qualified by the attribute 'type' whose value is charges_type
            # unfortunately, there are to child elements called total due to the hypothetical and actual charges living side by side
            self.prop_to_cdata_attr(detail_charge_items, "total", details_elem, "total", [("type", charges_type)])
    

    @property
    def hypotheticalecharges(self):
        """
        Return hypothetical energy charge totals on a per service basis
        """
        return self.echarges('hypothetical')


    @property
    def actualecharges(self):
        """
        Return actual energy charge totals on a per service basis
        """
        return self.echarges('actual')


    def echarges(self, charges_type):

        echarges = {}
        for detail_service in self.xpath("/ub:bill/ub:details/@service"):
            echarges[detail_service] = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (detail_service, charges_type))[0].text
            # convert it to decimal
            echarges[detail_service] = Decimal(echarges[detail_service])

        return echarges

    #TODO convenience method, depend on hypothetical_charges_details vs access xml directy here
    # or just make consumer depend on the main function instead
    @property
    def hypothetical_totals(self):
        hypothetical_totals = {}
        for service in self.xpath("/ub:bill/ub:details/@service"):
            total = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='hypothetical']" % service)[0].text
            hypothetical_totals[service] = Decimal(total).quantize(Decimal('.00'))

        return hypothetical_totals

    @hypothetical_totals.setter
    def hypothetical_totals(self, totals):
        for service in totals:
            self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='hypothetical']" % service)[0].text = str(totals[service])


    @property
    def motd(self):
        motd = self.xpath("/ub:bill/ub:rebill/ub:message")[0].text
        if motd is None: motd = ""
        return motd


    @property
    def statistics(self):

        statistics_elem_list = self.xpath("/ub:bill/ub:statistics")

        if not statistics_elem_list: 

            # there is no statistics element
            # TODO create one
            return None

        else:
            statistics_elem = statistics_elem_list[0]

            s = MutableNamedTuple()

            self.cdata_to_prop(statistics_elem, "conventionalconsumed", Decimal, s, "conventionalconsumed" )
            self.cdata_to_prop(statistics_elem, "renewableconsumed", Decimal, s, "renewableconsumed" )
            self.cdata_to_prop(statistics_elem, "renewableutilization", Decimal, s, "renewableutilization" )
            self.cdata_to_prop(statistics_elem, "conventionalutilization", Decimal, s, "conventionalutilization" )
            self.cdata_to_prop(statistics_elem, "renewableproduced", Decimal, s, "renewableproduced" )
            self.cdata_to_prop(statistics_elem, "co2offset", Decimal, s, "co2offset" )
            self.cdata_to_prop(statistics_elem, "totalsavings", Decimal, s, "totalsavings" )
            self.cdata_to_prop(statistics_elem, "totalrenewableconsumed", Decimal, s, "totalrenewableconsumed" )
            self.cdata_to_prop(statistics_elem, "totalrenewableproduced", Decimal, s, "totalrenewableproduced" )
            self.cdata_to_prop(statistics_elem, "totaltrees", Decimal, s, "totaltrees" )
            self.cdata_to_prop(statistics_elem, "totalco2offset", Decimal, s, "totalco2offset" )

            consumptiontrend_elem = statistics_elem.find("{bill}consumptiontrend")

            if consumptiontrend_elem is not None:
                # element exists, haven't seen children yet
                s.consumptiontrend = []

                period_elem_list = consumptiontrend_elem.findall("{bill}period")

                for period_elem in period_elem_list:
                    p = MutableNamedTuple()
                    self.attr_to_prop(period_elem, "quantity", Decimal, p, "quantity")
                    self.attr_to_prop(period_elem, "month", str, p, "month")
                    s.consumptiontrend.append(p)

        return s

    @statistics.setter
    def statistics(self, s):

        statistics_elem = self.xpath("/ub:bill/ub:statistics[1]")[0]

        # clear the immediate children, because present properties have to be added back in
        # document order.  It would be difficult to delete/create each child because
        # the insertion location would have to be tracked here.

        self.remove_children_named(statistics_elem, ["conventionalconsumed", "renewableconsumed", "renewableutilization",
            "conventionalutilization", "renewableproduced", "co2offset", "totalsavings", "totalrenewableconsumed",
            "totalrenewableproduced", "totaltrees", "totalco2offset"])

        self.prop_to_cdata(s, "conventionalconsumed", statistics_elem, "conventionalconsumed")
        self.prop_to_cdata(s, "renewableconsumed", statistics_elem, "renewableconsumed")
        self.prop_to_cdata(s, "renewableutilization", statistics_elem, "renewableutilization")
        self.prop_to_cdata(s, "conventionalutilization", statistics_elem, "conventionalutilization")
        self.prop_to_cdata(s, "renewableproduced", statistics_elem, "renewableproduced")
        self.prop_to_cdata(s, "co2offset", statistics_elem, "co2offset")
        self.prop_to_cdata(s, "totalsavings", statistics_elem, "totalsavings")
        self.prop_to_cdata(s, "totalrenewableconsumed", statistics_elem, "totalrenewableconsumed")
        self.prop_to_cdata(s, "totalrenewableproduced", statistics_elem, "totalrenewableproduced")
        self.prop_to_cdata(s, "totaltrees", statistics_elem, "totaltrees")
        self.prop_to_cdata(s, "totalco2offset", statistics_elem, "totalco2offset")

        # months are overwritten in a circular fashion
        for period in s.consumptiontrend:
            period_elem = statistics_elem.find("ub:consumptiontrend/ub:period[@month='%s']" % period.month, {"ub":"bill"})
            self.prop_to_attr(period, "month", period_elem, "month")
            self.prop_to_attr(period, "quantity", period_elem, "quantity")


if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-i", "--inputbill", dest="inputbill", help="Construct with bill", metavar="FILE")
    parser.add_option("-o", "--outputbill", dest="outputbill", help="", metavar="FILE")

    (options, args) = parser.parse_args()

    if (options.inputbill == None):
        print "Input bill must be specified."
        exit()

    bill = Bill(options.inputbill)

    #print bill.account
    #print bill.id

    #print bill.service_address
    #bill.service_address = bill.service_address
    #print bill.service_address 

    #print bill.rebill_periods
    #bill.rebill_periods = bill.rebill_periods
    #print bill.rebill_periods

    #print bill.utilbill_periods
    #utilbill_periods = bill.utilbill_periods
    #print [utilbill_periods[service] for service in utilbill_periods]

    #print bill.due_date

    #print bill.statistics

    #print bill.motd

    #m = bill.measured_usage
    #bill.measured_usage = m
    #m = bill.measured_usage


    #print bill.hypothetical_details

    #print bill.hypothetical_charges

    #r = bill.rebill_summary
    #print r
    #bill.rebill_summary = r
    #print bill.rebill_summary

    #t = bill.hypothetical_totals
    #print t
    #bill.hypothetical_totals = t

    #import pprint
    #pp = pprint.PrettyPrinter(indent=4)
    #m = bill.measured_usage
    #pp.pprint(m)
    #bill.measured_usage = m

    #d = bill.actual_details
    #print d
    #bill.actual_details = d
    #print bill.actual_details


    #s = bill.statistics
    #print s
    #bill.statistics = s

    c = bill.actual_charges
    print c
    bill.actual_charges = c
    c = bill.actual_charges
    print c

    #XMLUtils().save_xml_file(bill.xml(), options.outputbill, "prod", "prod")

