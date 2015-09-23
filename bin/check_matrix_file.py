#!/usr/bin/env python
import os
from sys import stderr

import click

from brokerage import quote_parsers
from core import init_config, init_altitude_db


@click.command(
    help='Check validation and parsing of a matrix quote file. SUPPLIER NAME '
         'can be any part of a name of one of the parser classes in the '
         'quote_parsers module (case insensitive).')
@click.argument('supplier_name')
@click.argument('file_path')
def read_file(supplier_name, file_path):
    def clean_name(name):
        return name.lower().replace(' ', '')

    with open(file_path, 'rb') as matrix_file:
        try:
            parser_class = next(
                getattr(quote_parsers, attr_name)
                for attr_name in dir(quote_parsers) if
                clean_name(attr_name).find(clean_name(supplier_name)) != -1)
        except StopIteration:
            print >> stderr, 'Unknown supplier:', supplier_name
            exit(1)

        print 'Using', parser_class.__name__
        parser = parser_class()

        parser.load_file(matrix_file, file_name=os.path.basename(file_path))
        parser.validate()
        print 'Validated'

        for quote in parser.extract_quotes():
            quote.validate()
        print 'Got %s quotes' % parser.get_count()


if __name__ == '__main__':
    init_config()
    init_altitude_db()
    read_file()
