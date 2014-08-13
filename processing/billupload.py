#!/usr/bin/python
import os
import sys
import errno
from uuid import uuid1
import re
from glob import glob
import shutil

sys.stdout = sys.stderr

# strings allowed as account names (formerly only digits, now digits/letters)
#ACCOUNT_NAME_REGEX = '[0-9]{5}'
ACCOUNT_NAME_REGEX = '[0-9a-z]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# strings allowed as sequence numbers
SEQUENCE_NUMBER_REGEX = '[0-9]+'

# extensions of utility bill formats we know we can convert into an image
# (order here determines order of preference for utility bill file lookup)
UTILBILL_EXTENSIONS = ['.pdf', '.html', '.htm', '.tif', '.tiff']

# extension of reebills (there probably won't be more than one format)
REEBILL_EXTENSION = 'pdf'

class BillUpload(object):

    def __init__(self, config, logger):
        #self.state_db = state_db
        self.config = config

        # directory where utility bill files are stored after being "deleted"
        self.utilbill_trash_dir = self.config.get('billdb',
                'utility_bill_trash_directory')
        
        self.logger = logger
        
        # load save directory info from config file
        self.save_directory = self.config.get('billdb', 'utilitybillpath')
        self.reebill_directory = self.config.get('billdb', 'billpath')

    def upload(self, utilbill, account, the_file, file_name):
        '''
        Uploads the file 'the_file' (whose name is 'file_name') to the
        location [SAVE_DIRECTORY]/[account]/[utilbill.id].[extension].
        '''
        # check account name (validate_account just checks it against a regex)
        # TODO: check that it's really an existing account against nexus
        if not validate_account(account):
            raise ValueError('invalid account name: "%s"' % account)
        # read whole file in one chunk
        try:
            data = the_file.read()
        except Exception as e:
            self.logger.error('unable to read "%s": %s' % \
                    (file_name, str(e)))
            raise
        finally:
            the_file.close()

        new_file_name=str(utilbill.id)+'.pdf'
        save_file_path = os.path.join(self.save_directory, account, new_file_name)

        # create the save directory if it doesn't exist
        create_directory_if_necessary(os.path.join(self.save_directory,
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
        return True

    def get_utilbill_file_path(self, utilbill, extension=None):
        '''Returns the path to the file containing the utility bill for the
        given account and dates.
        If 'extension' is given, the path to a hypothetical file is constructed
        and returned whether or not the file with that name exists.
        If 'extension' is not given, at least one bill file is assumed to exist
        and the one with the first extension found is chosen (extensions in
        'UTILBILL_EXTENSIONS' are chosen first, in order of their appearance
        there).
        An IOError will be raised if the file does not exist.'''

        # path to the bill file (in its original format):
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
        path_without_extension = os.path.join(self.save_directory,
                str(utilbill.customer.account), str(utilbill.id))
         
        if extension == None:
            # extension not provided, so look for an actual file that already
            # exists.
            # there could be multiple files with the same name but different
            # extensions. pick the one whose extension comes first in
            # UTILBILL_EXTENSIONS, if there is one. if not, it's an error
            i = 0
            for ext in UTILBILL_EXTENSIONS:
                if os.access(path_without_extension + ext, os.R_OK):
                    extension = ext
                    break
                i += 1
            if i == len(UTILBILL_EXTENSIONS):
                # pick the first file found with any extension that starts with
                # 'path_without_extension', if any
                choices = glob(path_without_extension + '*')
                if len(choices) > 0:
                    extension = os.path.splitext(choices[0])[1]
                else:
                    # no files match
                    raise IOError(('Could not find a readable bill file '
                            'whose path (without extension) is "%s"') %
                            path_without_extension)

        # if extension is provided, this is the path of a file that may not
        # (yet) exist
        return path_without_extension + extension

    def delete_utilbill_file(self, utilbill):
        '''Deletes the utility bill file given by account and period, by moving
        it to 'utilbill_trash_dir'. The path to the new file is returned.'''
        # TODO due to multiple services, utility bills cannot be uniquely
        # identified by account and period
        # see https://www.pivotaltracker.com/story/show/30079049
        path = self.get_utilbill_file_path(utilbill)
        deleted_file_name = 'deleted_utilbill_%s_%s' % (
                utilbill.customer.account, uuid1())
        new_path = os.path.join(self.utilbill_trash_dir, deleted_file_name)
        
        # create trash directory if it doesn't exist yet
        create_directory_if_necessary(self.utilbill_trash_dir, self.logger)

        # move the file
        shutil.move(path, new_path)

        return new_path

    def get_reebill_file_path(self, account, sequence):
        '''Return the path for the PDF file of the reebill given by account,
        sequence.
        '''
        return os.path.join(self.reebill_directory, account,
                '%s_%.4d.pdf' % (account, sequence))

def create_directory_if_necessary(path, logger):
    '''Creates the directory at 'path' if it does not exist and can be
    created.  If it cannot be created, logs the error using 'logger' and raises
    an exception.'''
    # TODO logging should be handled by BillToolBridge; just raise an exception
    # here and let BTB catch it and log it
    try:
        os.makedirs(path)
    except OSError as e:
        # if os.makedirs fails because 'path' already exists, that's good,
        # but all other errors are bad
        if e.errno != errno.EEXIST:
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

def validate_sequence_number(sequence):
    '''Returns true iff the sequence number is valid (just checks against a
    regex).'''
    try:
        return re.match(SEQUENCE_NUMBER_REGEX, sequence) is not None
    except TypeError:
        # re.match() accepts only 'str' and 'unicode' types; if account is not
        # even a string, it's definitely not valid
        return False
