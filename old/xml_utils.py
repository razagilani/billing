#!/usr/bin/python
""" Formerly: Utility functions useful for for a variety of XML related purposes.
Now only useful for save_xml_file(), which actually saves reebill data to both XML and MongoDB.
This file will eventually go away.
"""

from lxml import etree
from exceptions import TypeError
from urlparse import urlparse
import httplib
import string
import base64
import pymongo
import sys
from billing import mongo

class XMLUtils():

    def __init__(self):
        pass

    #TODO: clean up how file is handled - can be path, URI to a local file or remote http file
    #TODO: handle filesystem, error conditions
    def save_xml_file(self, xml, file, user=None, password=None):
        """ Saves to specified file where file is a path or HTTP URI. Also converts the XML into a Mongo document and saves it in skyline.reebill."""

        parts = urlparse(file)

        if (parts.scheme == 'http'): 
            # http scheme URL, PUT to eXistDB

            con = httplib.HTTPConnection(parts.netloc)
            con.putrequest('PUT', '%s' % file)
            con.putheader('Content-Type', 'text/xml')

            if (user and password):
                auth = 'Basic ' + string.strip(base64.encodestring(user + ':' + password))
                con.putheader('Authorization', auth )

            clen = len(xml) 
            con.putheader('Content-Length', clen)
            con.endheaders() 
            con.send(xml)
            response = con.getresponse()
            print str(response.status) + " " + response.reason

            print >> sys.stderr, file
        else:
            # plain files are never actually used

            # if not http specifier, assume just a plain filename was passed in.
            f = open(file, "w")
            f.write(xml)
            f.close()


    #TODO consider comparing tail text too
    def compare_xml(self, etree1, etree2):
        """ Use this function to compare element, attributes, attribute values and element text. """

        etree1_elems = [elem for elem in etree1.iter()]
        etree2_elems = [elem for elem in etree2.iter()]

        if (len(etree1_elems) != len(etree2_elems)):
            return (False, "Elements " + str(len(etree1_elems)) + " != " + str(len(etree2_elems)) + "\n")

        # Left to right comparison
        (success, reasons) = self.__compare(etree1, etree1_elems, etree2, etree2_elems)
        if (success == False):
            return (success, reasons)

        # Right to left comparison
        # TODO: pop elements that successfully compare from the first call of this function since remaining
        # ones don't exist and can be determined to not match and thus quickly added to the reasons list
        (success, reasons) = self.__compare(etree2, etree2_elems, etree1, etree1_elems)
        if (success == False):
            return (success, reasons)

        return (True, "Documents match")
            
    def __compare (self, etree1, etree1_elems, etree2, etree2_elems):
        """ Compare the list of elements from etree1 to etree2 plus all dependent child nodes such as attributes, """
        """ their values and text. """

        # For our purpose if namespaces are not the same, we've got two different docs
        etree1_ns = etree1.getroot().nsmap
        etree2_ns = etree2.getroot().nsmap
        if (etree1_ns != etree2_ns):
           return (False, "Namespace mismatch: " + str(etree1_ns) + " != " + str(etree2_ns))

        # compare element-wise with etree1
        for etree1_elem in etree1_elems:
            # for each element get an xpath to it
            xpath = etree1.getpath(etree1_elem)
            # and retrieve the element it identifies in etree2
            etree2_elem_list = etree2.xpath(xpath, namespaces=etree2_ns)
            # a fully qualified xpath should return one element or none
            if not (len(etree2_elem_list) <= 1): raise AssertionError

            # see if element matches. If so, see if text matches
            if (len(etree2_elem_list) == 0):
                return (False, "Element " + str(etree1_elem.tag) + " not found at " + xpath + "\n")
                
            # if both elements available then conditionally test attributes or text or both
            else:
                etree2_elem = etree2_elem_list[0]
                if (etree1_elem.text != etree2_elem.text):
                    return (False, "Text mismatch " + str(etree1_elem.tag) + " " + etree1_elem.text + " != " + etree2_elem.text + "\n")
                # compare attributes
                if (etree1_elem.attrib != etree2_elem.attrib):
                    return (False, "Attribute mismatch " + str(etree1_elem.attrib) + " != " + str(etree2_elem.attrib) + "\n")

                # compare attribute values
                for key in etree1_elem.attrib.keys():
                    if (etree2_elem.attrib[key] == None):
                        return (False, "Attribute value mismatch " + str(key))
                for key in etree2_elem.attrib.keys():
                    if (etree1_elem.attrib[key] == None):
                        return (False, "Attribute value mismatch " + str(key))
            
        return (True, None)

