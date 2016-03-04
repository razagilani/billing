#!/usr/bin/env python
"""Script to update matrix quote parsers and their tests with new example files.
"""
import re
import shutil
from importlib import import_module
from os.path import join, basename, splitext, isfile
from subprocess import check_call

import click
import desktop

from brokerage import quote_parsers
from test.test_brokerage import test_quote_parsers

QUOTE_FILES_DIR = 'test/test_brokerage/quote_files/'

@click.command(help='Update test code for a new matrix format.')
@click.argument('parser-name')
@click.argument('example-file-path')
def main(parser_name, example_file_path):
    # TODO: anything to change in the main code, not just test?
    main_module = getattr(quote_parsers, parser_name)

    # TODO: list all test modules, pick the ones whose FILE_NAME
    # matches the old example file name
    test_module_name = test_quote_parsers.__package__ + '.test_' + parser_name
    test_module = import_module(test_module_name)

    # find test file that uses this file
    test_file_path = test_module.__file__
    if test_module.__file__.endswith('pyc'):
        test_file_path = splitext(test_file_path)[0] + '.py'
        assert isfile(test_file_path)

    import ast
    with open(test_file_path) as test_file:
        p = ast.parse(test_file.read())
        test_class_name = next(node.name for node in ast.walk(p) if
                   isinstance(node, ast.ClassDef))
    test_class = getattr(test_module, test_class_name)

    # replace old example file with new one
    # (shell instead of hg library since we may not be using hg in the future)
    new_example_file_name = basename(example_file_path)
    new_example_file_path = join(QUOTE_FILES_DIR, new_example_file_name)
    shutil.copy(example_file_path, new_example_file_path)
    old_example_file_path = join(QUOTE_FILES_DIR, test_class.FILE_NAME)
    command = 'hg add "%s" && hg remove "%s"' % (new_example_file_path,
                                                 old_example_file_path)
    check_call(['/bin/bash', '--login', '-c', command])

    # update test file
    with open(test_file_path, 'r') as test_file:
        test_lines = test_file.read().splitlines()
    for i, line in enumerate(test_lines):
        if re.match('^\s+FILE_NAME = ', line):
            test_lines[i] = "FILE_NAME = '%s'" % new_example_file_name
            print test_lines[i]
            break
    with open(test_file_path, 'w') as test_file:
        test_file.write('\n'.join(test_lines))
        test_file.write('\n')

    # TODO: maybe run the parser class on the new file, and update
    # EXPECTED_COUNT, ALIASES, ...

    # open new example file in whatever program is used to view it
    desktop.open(new_example_file_path)

if __name__ == '__main__':
    main()
