#!/usr/bin/python
import os
import sys
import errno
import logging
import time
import re
import subprocess
import glob
import shutil
import ConfigParser
import MySQLdb
sys.stdout = sys.stderr
'''
TODO:
    move some of the constants below into the config file?
'''
# config file should always be in same directory as this file: set it to the
# path to the directory containing this file, relative to the program's current
# directory (which will be different if the code in this file is called from a
# different file
#CONFIG_FILE_PATH = os.dirname(__file__)
#CONFIG_FILE_PATH = os.path.join(os.getcwd(), 'billupload_config')
# according to bill_tool_bridge.py, the correct way is:
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), \
        'billupload_config')

# strings allowed as account names
ACCOUNT_NAME_REGEX = '[0-9]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# where account directories are located (uploaded files are saved inside of
# those)
# TODO: put in config file
SAVE_DIRECTORY = '/db-dev/skyline/utilitybills'

# extensions of utility bill formats we know we can convert into an image
UTILBILL_EXTENSIONS = ['pdf', 'html', 'htm', 'tif', 'tiff']

# where bill images are temporarily saved for viewing after they're rendered
# TODO change this to the real location
# TODO also put in config file
BILL_IMAGE_DIRECTORY = '/tmp/billimages'

# determines the format of bill image files
# TODO put in config file
IMAGE_EXTENSION = 'png'

# sampling density (pixels per inch?) for converting bills in a vector format
# (like PDF) to raster images
# if this is too big, rendering can be slow
# TODO put in config gile
IMAGE_RENDERING_DENSITY = 200

# default name of log file (config file can override this)
DEFAULT_LOG_FILE_NAME = 'billupload.log'

# default format of log entries (config file can override this)
DEFAULT_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# default database login info (config file can override this)
DEFAULT_DB_HOST = 'tyrell'
DEFAULT_DB_NAME = 'skyline_dev'
DEFAULT_DB_USERNAME = 'dev'
DEFAULT_DB_PASSWORD = 'dev'

class BillUpload(object):

    def __init__(self):
        # TODO: separate config-related code and use that also for 
        # bill_tool_bridge.py
        
        # if config file doesn't exist, create default version
        # (self.config.read() can fail in 2 ways: returns None if file doesn't
        # exist, raises exception in ConfigParser if the file is malformed.)
        self.config = ConfigParser.RawConfigParser()
        try:
            result = self.config.read(CONFIG_FILE_PATH)
            if not result:
                self.create_default_config_file()
        except:
            print >> sys.stderr, 'Config file at %s is malformed.' \
                    % CONFIG_FILE_PATH
            self.create_default_config_file()
        
        # get log file name and format from config file
        # TODO: if logging section of config file is malformed, choose default
        # values and report the error to stderr
        log_file_path = os.path.join( \
                os.path.dirname(os.path.realpath(__file__)), \
                self.config.get('log', 'log_file_name'))
        log_format = self.config.get('log', 'log_format')
        
        # make sure log file is writable
        try:
            open(log_file_path, 'a').close() # 'a' for append
        except Exception as e:
            # logging this error is impossible, so print to stderr
            print >> sys.stderr, 'Log file path "%s" is not writable.' \
                    % log_file_path
            raise
        
        # create logger
        self.logger = logging.getLogger('billupload')
        formatter = logging.Formatter(log_format)
        handler = logging.FileHandler(log_file_path)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler) 
        
        # load database login info from config file
        self.db_host = self.config.get('db', 'db_host')
        self.db_name = self.config.get('db', 'db_name')
        self.db_username = self.config.get('db', 'db_username')
        self.db_password = self.config.get('db', 'db_password')

        # clear out bill images directory
        # (if it fails, just log the error because it's not a critical problem)
        for root, dirs, files in os.walk(BILL_IMAGE_DIRECTORY):
            for aFile in files:
                try:
                    os.remove(os.path.join(root, aFile))
                except exception as e:
                    self.logger.warning(('couldn\'t remove "%s" when clearing \
                            "%s"' % (aFile, BILL_IMAGE_DIRECTORY)) + str(e))
            for aDir in dirs:
                try:
                    shutil.rmtree(aDir)
                except Exception as e:
                    self.logger.warning(('couldn\'t remove "%s" when clearing \
                            "%s"' % (aDir, BILL_IMAGE_DIRECTORY)) + str(e))

    '''Writes a config file with default values at CONFIG_FILE_PATH.'''
    def create_default_config_file(self):
        print "Creating default config file at", CONFIG_FILE_PATH

        # log file info
        self.config.add_section('log')
        self.config.set('log', 'log_file_name', DEFAULT_LOG_FILE_NAME)
        self.config.set('log', 'log_format', DEFAULT_LOG_FORMAT)

        # database login info
        self.config.add_section('db')
        self.config.set('db', 'db_host', DEFAULT_DB_HOST)
        self.config.set('db', 'db_name', DEFAULT_DB_NAME)
        self.config.set('db', 'db_username', DEFAULT_DB_USERNAME)
        self.config.set('db', 'db_password', DEFAULT_DB_PASSWORD)
        
        # write the file to CONFIG_FILE_PATH
        with open(CONFIG_FILE_PATH, 'wb') as new_config_file:
            self.config.write(new_config_file)
        
        # read from config file now that it must exist
        self.config.read(CONFIG_FILE_PATH)


    '''Uploads the file 'the_file' (whose name is 'file_name') to the location
    [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]. Returns
    True for success, or throws one of various exceptions if something doesn't
    work. (The caller takes care of reporting the error in the proper format.)
    '''
    def upload(self, account, begin_date, end_date, the_file, file_name):
        # check account name (validate_account just checks it against a regex)
        # TODO: check that it's really an existing account against nexus
        if not validate_account(account):
            self.logger.error('invalid account name: "%s"' % account)
            raise ValueError('invalid account name: "%s"' % account)

        # convert dates into the proper format, & report error if that fails
        try:
            formatted_begin_date = format_date(begin_date)
            formatted_end_date = format_date(end_date)
        except Exception as e:
            self.logger.error('unexpected date format(s): %s, %s: %s' \
                    % (begin_date, end_date, str(e)))
            raise
        
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
        save_file_path = os.path.join(SAVE_DIRECTORY, account, \
                formatted_begin_date + '-' + formatted_end_date \
                + os.path.splitext(file_name)[1])

        # create the save directory if it doesn't exist
        create_directory_if_necessary(os.path.join(SAVE_DIRECTORY, account),
                self.logger)
        
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
        self.insert_bill_in_database(account, begin_date, end_date)

        return True

    '''Inserts a a row into the utilbill table when the bill file has been
    uploaded.'''
    # TODO move all database-related code into state.py?
    # TODO use state.py fetch() function for database query
    def insert_bill_in_database(self, account, begin_date, end_date):
        conn = None
        try:
            conn = MySQLdb.connect(host=self.db_host, user=self.db_username, \
                    passwd=self.db_password, db=self.db_name)
            cur = conn.cursor(MySQLdb.cursors.DictCursor)
            # note that "select id from customer where account = '%s'" will be
            # null if the account doesn't exist, but in the future the account
            # will come from a drop-drown menu of existing accounts.
            result = cur.execute('''INSERT INTO utilbill
                    (id, customer_id, rebill_id, period_start, period_end,
                    estimated, received, processed) VALUES
                    (NULL, (select id from customer
                    where account = %s), NULL, %s, %s, FALSE, TRUE, FALSE)''',\
                    (account, begin_date, end_date))
            print result
        except MySQLdb.Error as e:
            self.logger.error('Database error when attempting to insert bill \
                    into utilbill for account %s from %s to %s: %s' \
                    % (account, begin_date, end_date, str(e)))
            raise
        except:
            # TODO: figure out how to trigger this error so it can be tested
            # (or better, find out what other exceptions can happen besides
            # MySQLdb.Error)
            self.logger.error('Unexpected error when attempting to insert bill \
                    into utilbill for account %s from %s to %s: %s'
                    % (account, begin_date, end_date, str(e)))
            raise
        finally:
            if conn is not None:
                conn.commit()
                conn.close()

    '''Given an account and dates for a utility bill, renders that bill as an
    image in BILL_IMAGE_DIRECTORY, and returns a path to that directory. (The
    caller is responsble for providing a URL to the client where that image can
    be accessed.)'''
    def getUtilBillImagePath(self, account, begin_date, end_date):
        # check account name (validate_account just checks that it's a string
        # and that it matches a regex)
        if not validate_account(account):
            self.logger.error('invalid account name: "%s"' % account)
            raise ValueError('invalid account name: "%s"' % account)

        # convert dates into the proper format, & report error if that fails
        try:
            formatted_begin_date = format_date(begin_date)
            formatted_end_date = format_date(end_date)
        except Exception as e:
            self.logger.error('unexpected date format(s): %s, %s: %s' \
                    % (begin_date, end_date, str(e)))
            raise

        # name of bill file (in its original format), without extension:
        # [begin_date]-[end_date].[extension]
        bill_file_name_without_extension = formatted_begin_date + '-' + \
                formatted_end_date

        # path to the bill file (in its original format):
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
        bill_file_path_without_extension = os.path.join(SAVE_DIRECTORY, \
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
            self.logger.error(error_text)
            raise IOError(error_text)
        bill_file_path = bill_file_path_without_extension + '.' + extension

        # name and path of bill image:
        bill_image_name_without_extension = 'utilbill_' + account + '_' \
                + bill_file_name_without_extension
        bill_image_path_without_extension = os.path.join(BILL_IMAGE_DIRECTORY,\
                bill_image_name_without_extension)

        # create bill image directory if it doesn't exist already
        create_directory_if_necessary(BILL_IMAGE_DIRECTORY, self.logger)
        
        # render the image, saving it to bill_image_path
        self.renderBillImage(bill_file_path, bill_image_path_without_extension)

        # return name of image file (the caller should know where to find the
        # image file)
        return bill_image_name_without_extension + '.' + IMAGE_EXTENSION


    '''Converts the file at [bill_file_path_without_extension].[extension] to
    an image and saves it at bill_image_path. Types are determined
    by extensions. (This requires the 'convert' command from ImageMagick, which
    itself requires html2pdf to render html files, and the 'montage' command
    from ImageMagick to join multi-page documents into a single image.) Raises
    an exception if image rendering fails.'''
    def renderBillImage(self, bill_file_path, \
            bill_image_path_without_extension):
        # use the command-line version of ImageMagick to convert the file.
        # ('-quiet' suppresses warning messages. formats are determined by
        # extensions.)
        # TODO: figure out how to really suppress warning messages; '-quiet'
        # doesn't stop it from printing "**** Warning: glyf overlaps cmap,
        # truncating." when converting pdfs
        convert_command = ['convert', '-quiet', '-density', \
                str(IMAGE_RENDERING_DENSITY), bill_file_path, \
                bill_image_path_without_extension + '.' + IMAGE_EXTENSION]
        convert_result = subprocess.Popen(convert_command, \
                stderr=subprocess.PIPE)

        # wait for 'convert' to finish (also sets convert_result.returncode)
        convert_result.wait()

        # if 'convert' failed, raise exception with the text that it printed to
        # stderr
        if convert_result.returncode != 0:
            error_text = convert_result.communicate()[1]
            self.logger.error('"%s" failed: %s' % (' '.join(convert_command), \
                    error_text))
            raise Exception(error_text)
        
        # if the original was a multi-page PDF, 'convert' may have produced
        # multiple images named bill_image_path-0.png, bill_image_path-1.png,
        # etc. get names of those
        # sorted() is necessary because glob doesn't guarantee order
        # TODO: possible bug: if there are leftover files whose names happen to
        # start with bill_image_path_without_extension, they'll be included
        # even if they shouldn't
        bill_image_names = sorted(glob.glob(bill_image_path_without_extension \
                + '-*.' + IMAGE_EXTENSION))
        
        # use ImageMagick's 'montage' command to join them
        if (len(bill_image_names) > 1):
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
                self.logger.error('"%s" failed: ' % (montage_command, \
                        bill_file_path, bill_image_path) + error_text)
                raise Exception(error_text)
        
            # delete the individual page images now that they've been joined
            for bill_image_name in bill_image_names:
                try:
                    os.remove(bill_image_name)
                except Exception as e:
                    # this is not critical, so if it fails, just log the error
                    self.logger.warning(('couldn\'t remove bill image file \
                            "%s": ' % bill_image_name) + str(e))
        

'''Creates the directory at 'path' if it does not exist and can be created.  If
it cannot be created, logs the error using 'logger' and raises an exception.'''
def create_directory_if_necessary(path, logger):
    try:
        os.makedirs(path)
    except OSError as e:
        # if os.makedirs() fails because 'path' already exists, that's good,
        # but all other errors are bad
        if e.errno == errno.EEXIST:
            pass
        else:
            logger.error('unable to create directory "%s": %s' \
                    % (path, str(e)))
            raise

# two "external validators" for checking accounts and dates ###################

'''Returns true iff the account is valid (just checks agains a regex, but this
removes dangerous input)'''
def validate_account(account):
    try:
        return re.match(ACCOUNT_NAME_REGEX, account) is not None
    except TypeError:
        # re.match() accepts only 'str' and 'unicode' types; if account is not
        # even a string, it's definitely not valid
        return False

'''Takes a date formatted according to INPUT_DATE_FORMAT and returns one
formatted according to OUTPUT_DATE_FORMAT. if the argument dose not match
INPUT_DATE_FORMAT, raises an exception.'''
def format_date(date_string):
    # convert to a time.struct_time object
    try:
        date_object = time.strptime(date_string, INPUT_DATE_FORMAT)
    except:
        raise
    # convert back
    return time.strftime(OUTPUT_DATE_FORMAT, date_object)

