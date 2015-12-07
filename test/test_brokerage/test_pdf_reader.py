"""Tests for PDFReader."""
import pytest

from brokerage.pdf_reader import PDFReader

EXAMPLE_FILE_PATH = 'test/test_brokerage/quote_files/Volunteer ' \
                    'Exchange_COH_2015 10-19-15.pdf'

@pytest.fixture()
def pdf_reader():
    """PDFReader instance with no file loaded."""
    return PDFReader()

@pytest.fixture()
def loaded_pdf_reader(pdf_reader):
    """PDFReader instance with the example file loaded."""
    with open(EXAMPLE_FILE_PATH) as example_file:
        pdf_reader.load_file(example_file, None)
    return pdf_reader

def test_load_file(pdf_reader):
    assert pdf_reader.is_loaded() is False
    with open(EXAMPLE_FILE_PATH) as example_file:
        pdf_reader.load_file(example_file, None)
    assert pdf_reader.is_loaded() is True

def test_get(loaded_pdf_reader):
    assert loaded_pdf_reader.get(1, 477, 70, basestring) == 'PREMIUM'
    # note that all values are strings
    assert loaded_pdf_reader.get(1, 487, 200, float) == '4.800'

def test_get_matches(loaded_pdf_reader):
    assert loaded_pdf_reader.get_matches(1, 477, 70, '(.*)', str) == 'PREMIUM'
    assert loaded_pdf_reader.get_matches(1, 487, 200, '(\d+.\d+)', float) == 4.8
