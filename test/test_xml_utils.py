import os
import unittest
import doctest
from skyliner.xml_utils import XMLUtils
from lxml import etree
from skyliner import sky_paths

class TestXMLUtils(unittest.TestCase):
    """Unit tests for test_utils"""

    def setUp(self):
        self.goodXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-complete.xml"))
        self.goodXMLNS = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-complete-ns.xml"))

    def test_number_elements(self):
        """compareXML returns false when the documents have different numbers of elements"""

        missingElemXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-missing-element.xml"))


        (result, reason) = XMLUtils().compare_xml(self.goodXML, missingElemXML)
        self.assertEqual(result, False, "Document element numbers unexpectedly match! " + reason)

        (result, reason) = XMLUtils().compare_xml(self.goodXML, self.goodXML)
        self.assertEqual(result, True, "Document element number does not match itself! " + reason)

    def test_number_elementsNS(self):
        """compareXML returns false when the documents have different numbers of elements with a namespace"""

        missingElemXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-missing-element-ns.xml"))


        (result, reason) = XMLUtils().compare_xml(self.goodXMLNS, missingElemXML)
        self.assertEqual(result, False, "Document element numbers unexpectedly match! " + reason)

        (result, reason) = XMLUtils().compare_xml(self.goodXMLNS, self.goodXMLNS)
        self.assertEqual(result, True, "Document element number does not match itself! " + reason)


    def test_element_name_equality(self):
        """compare_xml returns False when the document element names do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names.xml"))
        (result, reason) = XMLUtils().compare_xml(self.goodXML, wrongElemNameXML)
        self.assertEqual(result, False, "Document element names unexpectedly match! " + reason)

        (result, reason) = XMLUtils().compare_xml(self.goodXML, self.goodXML)
        self.assertEqual(result, True, "Document element names do not match itself! " + reason)


    def test_element_name_equality_ns(self):
        """compare_xml returns False when the document element names with namespace do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names-ns.xml"))
        (result, reason) = XMLUtils().compare_xml(self.goodXMLNS, wrongElemNameXML)
        self.assertEqual(result, False, "Document element names unexpectedly match! " + reason)


        (result, reason) = XMLUtils().compare_xml(self.goodXMLNS, self.goodXMLNS)
        self.assertEqual(result, True, "Document element names do not match itself! " + reason)

    def test_element_name_equality_ns_no_ns(self):
        """compare_xml returns False when the document element names with namespace do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names-ns.xml"))
        # now compare to the goodXML which has no namespace!
        (result, reason) = XMLUtils().compare_xml(wrongElemNameXML, self.goodXML)
        self.assertEqual(result, False, "Document element names unexpectedly match! " + reason)

        (result, reason) = XMLUtils().compare_xml(self.goodXML, self.goodXMLNS)
        self.assertEqual(result, False, "Documents with with the same elements but different namespaces match! " + reason)

    def test_compare_element_attributes(self):
        """ compare_xml returns false when attributes do not match. """

        wrongAttribsXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-attribs.xml"))

        (result, reason) = XMLUtils().compare_xml(wrongAttribsXML, self.goodXML)
        self.assertEqual(result, False, "Document attribs unexpectedly match! " + reason)

        missingAttribsXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-missing-attribs.xml"))

        (result, reason) = XMLUtils().compare_xml(missingAttribsXML, self.goodXML)
        self.assertEqual(result, False, "Document attribs unexpectedly match! " + reason)

    def test_compare_element_attribute_values(self):
        """ compare_xml returns false when the attribute values do not match. """

        wrongAttrValXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-attrib-value.xml"))

        (result, reason) = XMLUtils().compare_xml(wrongAttrValXML, self.goodXML)
        self.assertEqual(result, False, "Document attrib values unexpectedly match! " + reason)



    def test_compare_element_text(self):
        """compare_xml returns False when the document element text does not match"""

        wrongElemTextXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-text.xml"))

        (result, reason) = XMLUtils().compare_xml(wrongElemTextXML, self.goodXML)
        self.assertEqual(result, False, "Document element text unexpectedly matches! " + reason)


    def test_compare_all(self):
        """" see if a document successfully compares against itself."""

        (result, reason) = XMLUtils().compare_xml(self.goodXML, self.goodXML)
        self.assertEqual(result, True, "Document doesn't match itself! " + reason)





if __name__ == "__main__":
    unittest.main()
