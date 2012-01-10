#!/usr/bin/python
import os
import sys
import errno
import logging
import time
import datetime
import re
import subprocess
import glob
import shutil
import ConfigParser
from db_objects import Customer, UtilBill


sys.stdout = sys.stderr

# strings allowed as account names
ACCOUNT_NAME_REGEX = '[0-9]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# strings allowed as sequence numbers
SEQUENCE_NUMBER_REGEX = '[0-9]+'

# extensions of utility bill formats we know we can convert into an image
UTILBILL_EXTENSIONS = ['pdf', 'html', 'htm', 'tif', 'tiff']

# extension of reebills (there probably won't be more than one format)
REEBILL_EXTENSION = 'pdf'

# determines the format of bill image files
# TODO put in config file
IMAGE_EXTENSION = 'png'

# sampling density (pixels per inch?) for converting bills in a vector format
# (like PDF) to raster images
# if this is too big, rendering can be slow
IMAGE_RENDERING_DENSITY = 100


class BillUpload(object):

    def __init__(self, config, logger):
        #self.state_db = state_db
        self.config = config

        # get bill image directory from config file
        self.bill_image_directory = self.config.get('billrendering',
                'bill_image_directory')
        
        self.logger = logger
        
        # load save directory info from config file
        self.save_directory = self.config.get('billdb', 'utilitybillpath')
        self.reebill_directory = self.config.get('billdb', 'billpath')

    def upload(self, account, begin_date, end_date, the_file, file_name):
        '''Uploads the file 'the_file' (whose name is 'file_name') to the
        location
        [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]. Returns
        True for success, or throws one of various exceptions if something
        doesn't work. (The caller takes care of reporting the error in the
        proper format.) '''
        # check account name (validate_account just checks it against a regex)
        # TODO: check that it's really an existing account against nexus
        if not validate_account(account):
            raise ValueError('invalid account name: "%s"' % account)

        # convert dates into the proper format, & report error if that fails
        try:
            formatted_begin_date = format_date(begin_date)
            formatted_end_date = format_date(end_date)
        except Exception as e:
            raise ValueError('unexpected date format(s): %s, %s: %s' \
                    % (begin_date, end_date, str(e)))
        
        # read whole file in one chunk
        try:
            data = the_file.read()
        except Exception as e:
            self.logger.error('unable to read "%s": %s' % \
                    (file_name, str(e)))
            raise
        finally:
            the_file.close()
        
        # path where file will be saved:
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension] (NB:
        # date format is determined by the submitter)
        save_file_path = os.path.join(self.save_directory, account,
                formatted_begin_date + '-' + formatted_end_date \
                + os.path.splitext(file_name)[1])

        # create the save directory if it doesn't exist
        create_directory_if_necessary(os.path.join( self.save_directory,
                account), self.logger)
        
        # write the file in SAVE_DIRECTORY
        # (overwrite if it's already there)
        save_file = None
        try:
            save_file = open(save_file_path, 'w')
            save_file.write(data)
        except Exception as e:
            self.logger.error('unable to write "%s": %s' \
                    % (save_file_path, str(e)))
            raise
        finally:
            if save_file is not None:
                save_file.close()

        # make a row in utilbill representing the bill that was uploaded.
        #self.state_db.insert_bill_in_database(account, begin_date, end_date)

        return True


    # TODO rename: ImagePath -> ImageName
    def getUtilBillImagePath(self, account, begin_date, end_date, resolution):
        '''Given an account and dates for a utility bill, renders that bill as
        an image in BILL_IMAGE_DIRECTORY, and returns the name of the image
        file. (The caller is responsble for providing a URL to the client where
        that image can be accessed.)'''
        # check account name (validate_account just checks that it's a string
        # and that it matches a regex)
        if not validate_account(account):
            raise ValueError('invalid account name: "%s"' % account)

        # convert dates into the proper format, & report error if that fails
        try:
            formatted_begin_date = format_date(begin_date)
            formatted_end_date = format_date(end_date)
        except Exception as e:
            raise ValueError('unexpected date format(s): %s, %s: %s' \
                    % (begin_date, end_date, str(e)))

        # name of bill file (in its original format), without extension:
        # [begin_date]-[end_date].[extension]
        bill_file_name_without_extension = formatted_begin_date + '-' + \
                formatted_end_date

        # path to the bill file (in its original format):
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
        bill_file_path_without_extension = os.path.join(self.save_directory, \
                account, bill_file_name_without_extension)
         
        # there could be multiple files with the same name but different
        # extensions. pick the one whose extension comes first in
        # UTILBILL_EXTENSIONS, if there is one. if not, it's an error
        i = 0
        for ext in UTILBILL_EXTENSIONS:
            if os.access(bill_file_path_without_extension+'.'+ext, os.R_OK):
                extension = ext
                break
            i += 1
        if i == len(UTILBILL_EXTENSIONS):
            error_text = 'Could not find a readable bill file whose path \
                    (without extension) is "%s"' \
                    % bill_file_path_without_extension
            raise IOError(error_text)
        bill_file_path = bill_file_path_without_extension + '.' + extension

        # name and path of bill image: name includes date so it's always unique
        bill_image_name_without_extension = 'utilbill_' + account + '_' \
                + bill_file_name_without_extension + '_' + \
                str(datetime.datetime.today()).replace(' ', '') \
                .replace('.','').replace(':','')
        bill_image_path_without_extension = os.path.join(
                self.bill_image_directory,
                bill_image_name_without_extension)

        # create bill image directory if it doesn't exist already
        create_directory_if_necessary(self.bill_image_directory, self.logger)

        # render the image, saving it to bill_image_path
        self.renderBillImage(bill_file_path, bill_image_path_without_extension,
                extension, resolution)
        
        # return name of image file (the caller should know where to find the
        # image file)
        return bill_image_name_without_extension + '.' + IMAGE_EXTENSION
        

    # TODO rename: ImagePath -> ImageName
    def getReeBillImagePath(self, account, sequence, resolution):
        '''Given an account number and sequence number of a reebill, remnders
        that bill as an image in self.bill_image_directory, and returns the
        name of the image file. ("Sequence" means the position of that bill in
        the sequence of bills issued to a particular customer.) The caller is
        responsble for providing a URL to the client where that image can be
        accessed.'''
        # check account name (validate_account just checks that it's a string
        # and that it matches a regex)
        if not validate_account(account):
            raise ValueError('invalid account name: "%s"' % account)

        # check sequence number
        if not validate_sequence_number(sequence):
            raise ValueError('invalid sequence number: "%s"' % account)

        # get path of reebill
        reebill_file_path = os.path.join(self.reebill_directory, account, \
                sequence + '.' + REEBILL_EXTENSION)

        # make sure it exists and can be read
        if not os.access(reebill_file_path, os.R_OK):
            error_text = 'Could not find the reebill "%s"' % reebill_file_path
            raise IOError(error_text)

        # name and path of bill image: name includes date so it's always unique
        bill_image_name_without_extension = 'reebill_' + account + '_' \
                + sequence + str(datetime.datetime.today()).replace(' ', '') \
                .replace('.','').replace(':','')
        bill_image_path_without_extension = os.path.join(
                self.bill_image_directory,
                bill_image_name_without_extension)

        # create bill image directory if it doesn't exist already
        create_directory_if_necessary(self.bill_image_directory, self.logger)
        
        # render the image, saving it to bill_image_path
        self.renderBillImage(reebill_file_path, 
                bill_image_path_without_extension, REEBILL_EXTENSION,
                resolution)

        # return name of image file (the caller should know where to find the
        # image file)
        return bill_image_name_without_extension + '.' + IMAGE_EXTENSION


    def renderBillImage(self, bill_file_path, \
            bill_image_path_without_extension, extension, density):
        '''Converts the file at [bill_file_path_without_extension].[extension]
        to an image and saves it at bill_image_path. Types are determined by
        extensions. For non-raster input formats like PDF, the resolution of
        the output image is determined by 'density' (in pixels per inch?).
        (This requires the 'convert' command from ImageMagick, which itself
        requires html2pdf to render html files, and the 'montage' command from
        ImageMagick to join multi-page documents into a single image.) Raises
        an exception if image rendering fails.'''

        # TODO: this needs to be reimplemented so as to be command line command
        # oriented It is not possible to make a generic function for N command
        # line programs

        if extension == "pdf".lower():
            convert_command = ['pdftoppm', '-png', '-rx', \
                    str(density), '-ry', str(density), bill_file_path, \
                    bill_image_path_without_extension]
        else:
            # use the command-line version of ImageMagick to convert the file.
            # ('-quiet' suppresses warning messages. formats are determined by
            # extensions.)
            # TODO: figure out how to really suppress warning messages; '-quiet'
            # doesn't stop it from printing "**** Warning: glyf overlaps cmap,
            # truncating." when converting pdfs
            convert_command = ['convert', '-quiet', '-density', \
                    str(density), bill_file_path, \
                    bill_image_path_without_extension + '.' + IMAGE_EXTENSION]

        convert_result = subprocess.Popen(convert_command, \
                stderr=subprocess.PIPE)

        # wait for 'convert' to finish (also sets convert_result.returncode)
        convert_result.wait()

        # if 'convert' failed, raise exception with the text that it printed to
        # stderr
        if convert_result.returncode != 0:
            error_text = convert_result.communicate()[1]
            raise Exception('"%s" failed: %s' % (' '.join(convert_command), \
                    error_text))
        
        # if the original was a multi-page PDF, 'convert' may have produced
        # multiple images named bill_image_path-0.png, bill_image_path-1.png,
        # etc. get names of those
        # sorted() is necessary because glob doesn't guarantee order
        # TODO: possible bug: if there are leftover files whose names happen to
        # start with bill_image_path_without_extension, they'll be included
        # even if they shouldn't
        bill_image_names = sorted(glob.glob(bill_image_path_without_extension \
                + '-*.' + IMAGE_EXTENSION))

        # always use ImageMagick's 'montage' command to join them
        # since pdftoppm always outputs a '-1' even if there is only one page
        # convert will only output a '-N' if there are more than one page
        #if (len(bill_image_names) > 1):
        montage_command = ['montage'] + bill_image_names + \
                ['-geometry', '+1+1', '-tile', '1x', \
                bill_image_path_without_extension + '.' + IMAGE_EXTENSION]
        montage_result = subprocess.Popen(montage_command, \
                stderr=subprocess.PIPE)
    
        # wait for 'montage' to finish (also sets
        # montage_result.returncode)
        montage_result.wait()
    
        # if 'montage' failed, raise exception with the text that
        # it printed to stderr
        if montage_result.returncode != 0:
            error_text = montage_result.communicate()[1]
            raise Exception('"%s %s %s" failed: ' % (montage_command, \
                    bill_file_path, bill_image_path_without_extension) \
                    + error_text)
    
        # delete the individual page images now that they've been joined
        for bill_image_name in bill_image_names:
            try:
                os.remove(bill_image_name)
            except Exception as e:
                # this is not critical, so if it fails, just log the error
                self.logger.warning((('couldn\'t remove bill image file '
                        '"%s": ') % bill_image_name) + str(e))
        

def create_directory_if_necessary(path, logger):
    '''Creates the directory at 'path' if it does not exist and can be
    created.  If it cannot be created, logs the error using 'logger' and raises
    an exception.'''
    try:
        os.makedirs(path)
    except OSError as e:
        # if os.makedirs() fails because 'path' already exists, that's good,
        # but all other errors are bad
        if e.errno == errno.EEXIST:
            pass
        else:
            logger.error('unable to create directory "%s": %s'  % (path, e))
            raise

# validators for checking parameter values #####################################

def validate_account(account):
    '''Returns true iff the account is valid (just checks agains a regex, but
    this removes dangerous input)'''
    try:
        return re.match(ACCOUNT_NAME_REGEX, account) is not None
    except TypeError:
        # re.match() accepts only 'str' and 'unicode' types; if account is not
        # even a string, it's definitely not valid
        return False

def format_date(date_string):
    '''Takes a date formatted according to INPUT_DATE_FORMAT and returns one
    formatted according to OUTPUT_DATE_FORMAT. if the argument dose not match
    INPUT_DATE_FORMAT, raises an exception.'''
    # convert to a time.struct_time object
    try:
        date_object = time.strptime(date_string, INPUT_DATE_FORMAT)
    except:
        raise
    # convert back
    return time.strftime(OUTPUT_DATE_FORMAT, date_object)

def validate_sequence_number(sequence):
    '''Returns true iff the sequence number is valid (just checks against a
    regex).'''
    try:
        return re.match(SEQUENCE_NUMBER_REGEX, sequence) is not None
    except TypeError:
        # re.match() accepts only 'str' and 'unicode' types; if account is not
        # even a string, it's definitely not valid
        return False
