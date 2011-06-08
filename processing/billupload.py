#!/usr/bin/python
import os
import errno
import logging
import time
import re

# TODO: is this what you mean by prepending the module directory?
CONFIG_FILE_PATH = os.path.join(os.getcwd(), 'billupload_config')

# strings allowed as account names
ACCOUNT_NAME_REGEX = '[0-9]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# where account directories are located (uploaded files are saved inside of
# those)
# TODO: change this directory?
SAVE_DIRECTORY = '/tmp'

# format of error messages in the log file
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'


class BillUpload(object):

    def __init__(self):
        # read config file if it exists
        config_file = None
        try:
            config_file = open(CONFIG_FILE_PATH)
            for index, line in enumerate(config_file.read().split('\n')):
                if index == 0:
                    self.log_file = line
                else:
                    # TODO: what if there was no config in the file?
                    pass
        except IOError as e:
            #TODO: what should i do if the file doesn't exist? create it with
            # default values, use default values without creating the file, or
            # just exit?
            print e
            exit()
        finally:
            if config_file != None:
                config_file.close()

        
        # TODO make sure log file is writable?
        
        # create logger
        self.logger = logging.getLogger('billupload')
        formatter = logging.Formatter(LOG_FORMAT)
        handler = logging.FileHandler(self.log_file)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler) 
    
   
    def upload(self, account, begin_date, end_date, file_to_upload):
        # this method just passes the arguments along to upload_bill and
        # reports the result in JSON format so there's no JSON mixed into the
        # real code
        if upload_bill(account, begin_date, end_date, file_to_upload):
            return '{success: true}'
        return '{sucess: false}'

    def upload_bill(self, account, begin_date, end_date, file_to_upload):
        # check account name (removes malicious input, e.g. starting with '../')
        # TODO: check that it's really an existing account?
        if not re.match(ACCOUNT_NAME_REGEX, account):
            logger.error('invalid account name: "%s"' % account)
            # TODO raise exception? Perhaps an external validator can do this work since it
            # is not directly related to uploading and saving files
            return False
        
        # convert dates from string to python's 'time.struct_time' type, and back,
        # to get formatted dates
        try:
            begin_date_object = time.strptime(begin_date, INPUT_DATE_FORMAT)
            end_date_object = time.strptime(end_date, INPUT_DATE_FORMAT)
        except Exception as e:
            logger.error('unexpected date format(s): %s, %s\n%s' \
                    % (begin_date, end_date, str(e)))
            # TODO raise exception? Perhaps an external validator can do this work since it
            # is not directly related to uploading and saving files
            return False
        formatted_begin_date = time.strftime(OUTPUT_DATE_FORMAT, begin_date_object)
        formatted_end_date = time.strftime(OUTPUT_DATE_FORMAT, end_date_object)
        
        # read whole file in one chunk
        try:
            data = file_to_upload.file.read()
        except:
            logger.error('unable to read "' + file_to_upload.filename + '"')
            # TODO raise exception
            return False
        finally:
            file_to_upload.file.close()
        
        # path where file will be saved:
        # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
        # (NB: date format is determined by the submitter)
        save_file_path = os.path.join(SAVE_DIRECTORY, account, \
                formatted_begin_date + '-' + formatted_end_date \
                + os.path.splitext(file_to_upload.filename)[1])

        # create the save directory if it doesn't exist
        try:
            os.makedirs(os.path.join(SAVE_DIRECTORY, account))
        except OSError as error:
            if error.errno == errno.EEXIST:
                pass
            else:
                logger.error('unable to create directory "%"' \
                        % os.path.join(SAVE_DIRECTORY, save_file_path));
                # TODO raise exception
                return False
        
        # write the file in SAVE_DIRECTORY
        save_file = open(save_file_path, 'w')
        try:
            save_file.write(data)
        except:
            logger.error('unable to write "' + save_file_path + '"')
            # TODO raise exception
            return False
        finally:
            save_file.close()

        return True

