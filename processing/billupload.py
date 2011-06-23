#!/usr/bin/python
import os
import sys
import errno
import logging
import time
import re
import ConfigParser
import MySQLdb
sys.stdout = sys.stderr
'''
This was supposed to be completely independent of cherrypy, but cherrypy passes the file argument as a cherrypy object, not a string or file object. See comment on BillUpload.upload().  Note that this problem also makes it hard to write tests or a command-line interface.

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
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),'billupload_config')

# strings allowed as account names
ACCOUNT_NAME_REGEX = '[0-9]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# where account directories are located (uploaded files are saved inside of
# those)
# TODO: put in config file
SAVE_DIRECTORY = '/db/skyline/utilitybills'

# where bill images are temporarily saved for viewing after they're rendered
# TODO change this to the real location
# TODO also put in config file
BILL_IMAGE_DIRECTORY = '/tmp/billimages'

# default name of log file (config file can override this)
DEFAULT_LOG_FILE_NAME = 'billupload.log'

# default format of log entries (config file can override this)
DEFAULT_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

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


    '''Writes a config file with default values at CONFIG_FILE_PATH.'''
    def create_default_config_file(self):
        print "Creating default config file at", CONFIG_FILE_PATH
        self.config.add_section('log')
        self.config.set('log', 'log_file_name', DEFAULT_LOG_FILE_NAME)
        self.config.set('log', 'log_format', DEFAULT_LOG_FORMAT)
        
        # write the file to CONFIG_FILE_PATH
        with open(CONFIG_FILE_PATH, 'wb') as new_config_file:
            self.config.write(new_config_file)
        
        # read from config file now that it must exist
        self.config.read(CONFIG_FILE_PATH)


    '''Uploads the file given by file_to_upload to the location
    [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]. Returns
    True for success, or throws one of various exceptions if something doesn't
    work. (The caller takes care of reporting the error in the proper format.)
    Note that account, begin_date, and end_date are strings, but file_to_upload
    is a cherrypy object of class 'cherrypy._cpreqbody.Part'--so it's hard to
    completely remove cherrypy dependency from this file. '''
    # TODO: remove cherrypy dependency. caller should extract the actual file
    # from cherrypy's object and pass that as 'file_to_upload'
    def upload(self, account, begin_date, end_date, file_to_upload):
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
            data = file_to_upload.file.read()
        except Exception as e:
            self.logger.error('unable to read "%s": %s' % \
                    (file_to_upload.filename, str(e)))
            raise
        finally:
            file_to_upload.file.close()
        
        # path where file will be saved:
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension] (NB:
        # date format is determined by the submitter)
        save_file_path = os.path.join(SAVE_DIRECTORY, account, \
                formatted_begin_date + '-' + formatted_end_date \
                + os.path.splitext(file_to_upload.filename)[1])

        # create the save directory if it doesn't exist
        try:
            os.makedirs(os.path.join(SAVE_DIRECTORY, account))
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                self.logger.error('unable to create directory "%s": %s' \
                        % (os.path.join(SAVE_DIRECTORY, save_file_path), \
                        str(e)))
                raise    
        
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

    '''Inserts a a row into the utilbill table when the bill file has been uploaded.'''
    # TODO move all database-related code into state.py?
    # TODO use state.py fetch() function for database query
    def insert_bill_in_database(self, account, begin_date, end_date):
        conn = None
        try:
            conn = MySQLdb.connect(host='tyrell', user='dev', passwd='dev', db='skyline_dev')
            cur = conn.cursor(MySQLdb.cursors.DictCursor)
            # note that "select id from customer where account = '%s'" will be
            # null if the account doesn't exist, but in the future the account
            # will come from a drop-drown menu of existing accounts.
            result = cur.execute('''INSERT INTO skyline_dev.utilbill
                    (id, customer_id, rebill_id, period_start, period_end,
                    estimated, received, processed) VALUES
                    (NULL, (select id from skyline_dev.customer where account = %s),
                    NULL, %s, %s, FALSE, TRUE, FALSE)''' , \
                    (account, begin_date, end_date))
            print result
        except MySQLdb.Error:
            # TODO log errors?
            print "Database error"
            raise
        except:
            print "Unexpected error:", sys.exc_info()[0]
            raise
        finally:
            if conn is not None:
                conn.commit()
                conn.close()

    '''Given an account and dates for a bill, renders that bill as an image in
    a certain directory, and returns a path to that directory. (The caller is
    responsble for providing a URL to the client where that image can be accessed.)'''
    def getBillImagePath(self, account, begin_date, end_date):
        # check account name (validate_account just checks that it's a string and that it matches a regex)
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

        # TODO create bill image directory if it doesn't exist already
        
        # name of bill file (in its original format), without extension:
        # [begin_date]-[end_date].[extension]
        bill_file_name_without_extension = formatted_begin_date + '-' + \
                formatted_end_date

        # path to the bill file (in its original format):
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
        bill_file_path_without_extension = os.path.join(SAVE_DIRECTORY, \
                account, bill_file_name_without_extension)
         
        # there could be multiple files with the same name but different
        # extensions. that shouldn't happen, but if it does, look for a pdf
        # first and html second.
        # TODO add any other file types that might occur
        if os.access(bill_file_path_without_extension + '.pdf', os.R_OK):
            extension = 'pdf'
        elif os.access(bill_file_path_without_extension + '.html', os.R_OK):
            extension = 'html'
        else:
            raise IOError('Could not find a readable bill file whose path (without extension) is "%s"' % bill_file_path_without_extension)
        bill_file_path = bill_file_path_without_extension + '.' + extension

        # name and path of bill image:
        # TODO decide how image should actually be named
        bill_image_name = 'image_' + account + '_' + bill_file_name_without_extension + '.' + extension
        bill_image_path = os.path.join(BILL_IMAGE_DIRECTORY, bill_image_name)

        # render the image, saving it to bill_image_path
        self.renderBillImage(bill_file_path, bill_image_path)
        
        # return name of image file (the caller should know where to find the image file)
        return bill_image_name

    '''Converts the file at bill_file_path to a PNG image and saves it at
    bill_image_path.'''
    def renderBillImage(self, bill_file_path, bill_image_path):
        # TODO don't do this with shell commands, add error checking, etc!
        os.popen('cp %s %s' % (bill_file_path, bill_image_path))
        os.popen('echo "%s" /tmp/billimages/out' % bill_image_path)
        

# two "external validators" for checking accounts and dates ###################

'''Returns true iff the account is valid (just checks agains a regex, but this
removes dangerous input)'''
def validate_account(account):
    if type(account) is not str:
        return False
    return re.match(ACCOUNT_NAME_REGEX, account) is not None

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

