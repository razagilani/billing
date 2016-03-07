#!/usr/bin/env python
"""A useful script for analyzing PDF files.
"""
import click
from pdfminer.layout import LTTextBox

from util.pdf import PDFUtil


@click.command(
    help='Print out coordinates and contents of text elements in a PDF file '
         '(x0, y0, x1, y1).')
@click.argument('file_path')
@click.option('--round-coordinates', '-r', is_flag=True,
              help='Round all coordinates to integers.')
def main(file_path, round_coordinates=False):
    with open(file_path) as pdf_file:
        pages = PDFUtil().get_pdfminer_layout(pdf_file)

    for i, page in enumerate(pages):
        print 'page', i + 1
        for element in page:
            if isinstance(element, LTTextBox):
                x0, y0, x1, y1 = element.x0, element.y0, element.x1, element.y1
                if round_coordinates:
                    x0, y0, x1, y1 = (int(num) for num in (x0, y0, x1, y1))
                print '%s,%s %s,%s %s: ' % (
                    x0, y0, x1, y1, repr(element.get_text()))
        print ''

if __name__ == '__main__':
    main()

