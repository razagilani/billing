import os
from abc import ABCMeta
from os.path import splitext

from testfixtures import TempDirectory

from core import ROOT_PATH
from core.exceptions import BillingError
from util.shell import shell_quote, run_command_in_shell


class Converter(object):
    """Base for utility classes that convert a file from one type to another
    by writing a temporary file and then running another program to convert
    that into an output file. All this happens in a temporary directory that
    should get automatically cleaned up.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        self.directory = TempDirectory()

    def get_command(self, temp_file_path, converted_file_path):
        """Override to return the command that should be run to do file
        conversion. This gets run in a login shell so it can (and should) use
        the PATH.
        """
        raise NotImplementedError

    def get_converted_file_path(self, temp_file_path):
        """Override to return the path to the converted file, if not the same
        as the input file.
        """
        return temp_file_path

    def convert_file(self, fp, file_name):
        """
        Conversion is done here. Doesn't need ot be overridden in subclasses.
        :param fp: original file
        :param file_name: name of the original file including extension
        :return: converted file opened in 'rb' mode
        """
        temp_file_path = os.path.join(self.directory.path, file_name)
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(fp.read())
        converted_file_path = self.get_converted_file_path(temp_file_path)
        command = self.get_command(temp_file_path, converted_file_path)
        _, _, check_exit_status = run_command_in_shell(command)

        # note: libreoffice exits with 0 even if it failed to convert. errors
        # are detected by checking whether the destination file exists.
        check_exit_status()
        if not os.access(converted_file_path, os.R_OK):
            raise BillingError('Failed to convert file "%s" to %s' % (
                file_name, converted_file_path))
        return open(converted_file_path, 'rb')

    def __del__(self):
        self.directory.cleanup()


class LibreOfficeFileConverter(Converter):
    """Converts MS Office/LibreOffice files from one type to another using
    the LibreOffice command-line interface.
    It would be better to use a library (such as "uno", "unotools", or "unoconv"
    which are Python interfaces to the same code used in LibreOffice).
    """
    # the LibreOffice executable is called "soffice". its location is
    # environment-dependent so it must be added to the PATH in deployment
    # environments and local development environments.
    SOFFICE_PATH = 'soffice'

    def __init__(self, destination_extension, destination_type_str):
        """
        :param destination_extension: file extension representing the
        type of the converted file, such as "xls".
        :param destination_type_str: a special string used by LibreOffice
        that determines the details of the file type, such as "xls:MS Excel 97"
        (usually starts with destination_extension).
        """
        super(LibreOfficeFileConverter, self).__init__()
        self.destination_extension = destination_extension
        self.destination_type_str = destination_type_str

    def get_converted_file_path(self, temp_file_path):
        return '.'.join(
            [splitext(temp_file_path)[0], self.destination_extension])

    def get_command(self, temp_file_path, converted_file_path):
        return '%s --headless --convert-to %s --outdir %s %s' % (
            self.SOFFICE_PATH, self.destination_type_str,
            self.directory.path,
            shell_quote(temp_file_path))


class TabulaConverter(Converter):
    """Extracts tabular data from PDF files using Tabula-java
    (see https://github.com/tabulapdf/tabula-java).
    """
    # Tabula jar file is included in the repository so we don't have to deal
    # with installation or handle different paths in different environments.
    TABULA_PATH = os.path.join(ROOT_PATH, 'bin',
                               'tabula-0.8.0-jar-with-dependencies.jar')

    def get_converted_file_path(self, temp_file_path):
        return '.'.join([splitext(temp_file_path)[0], 'csv'])

    def get_command(self, temp_file_path, converted_file_path):
        return 'java -jar %s --pages all -o %s %s' % (
            self.TABULA_PATH, shell_quote(converted_file_path),
            shell_quote(temp_file_path))
