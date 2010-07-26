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


        (result, reason) = XMLUtils().compare_element_count(self.goodXML, missingElemXML)
        self.assertEqual(result, False, "Document element numbers unexpectedly match!" + reason)

        (result, reason) = XMLUtils().compare_element_count(self.goodXML, self.goodXML)
        self.assertEqual(result, True, "Document element number does not match itself!" + reason)

    def test_number_elementsNS(self):
        """compareXML returns false when the documents have different numbers of elements with a namespace"""

        missingElemXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-missing-element-ns.xml"))


        (result, reason) = XMLUtils().compare_element_count(self.goodXMLNS, missingElemXML)
        self.assertEqual(result, False, "Document element numbers unexpectedly match!" + reason)

        (result, reason) = XMLUtils().compare_element_count(self.goodXMLNS, self.goodXMLNS)
        self.assertEqual(result, True, "Document element number does not match itself!" + reason)


    def test_element_name_equality(self):
        """CompareXML returns False when the document element names do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names.xml"))
        (result, reason) = XMLUtils().compare_element_names(self.goodXML, wrongElemNameXML)
        self.assertEqual(result, False, "Document element names unexpectedly match!" + reason)

        (result, reason) = XMLUtils().compare_element_names(self.goodXML, self.goodXML)
        self.assertEqual(result, True, "Document element names do not match itself!" + reason)


    def test_element_name_equality_ns(self):
        """CompareXML returns False when the document element names with namespace do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names-ns.xml"))
        (result, reason) = XMLUtils().compare_element_names(self.goodXMLNS, wrongElemNameXML)
        self.assertEqual(result, False, "Document element names unexpectedly match!" + reason)


        (result, reason) = XMLUtils().compare_element_names(self.goodXMLNS, self.goodXMLNS)
        self.assertEqual(result, True, "Document element names do not match itself!" + reason)

    def test_element_name_equality_ns_no_ns(self):
        """CompareXML returns False when the document element names with namespace do not match"""

        wrongElemNameXML = etree.parse(os.path.join("test", "test_xml_utils_data", "compareXML-wrong-elem-names-ns.xml"))
        (result, reason) = XMLUtils().compare_element_names(wrongElemNameXML, self.goodXML)
        self.assertEqual(result, False, "Document element names unexpectedly match!" + reason)


        (result, reason) = XMLUtils().compare_element_names(self.goodXML, self.goodXMLNS)
        self.assertEqual(result, True, "Document element names do not match itself!" + reason)



    def test_compare_element_attributes(self):
        self.assertEqual(1, 0, "Implement test and then logic")

    def test_compare_element_text(self):
        self.assertEqual(1, 0, "Implement test and then logic")


if __name__ == "__main__":
    unittest.main()
