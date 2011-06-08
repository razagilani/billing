#!/usr/bin/python
import os
import errno
import logging
import time
import re

'''
questions:

- "Check in a 'dummy' config file. Usually name it filename-dev.config and another filename-prod.config.  Or, have the code create the file which is then hg ignored.  Don't ever write config file code - there is always a framework, and that framework is being used where your code was integrated, and is using python module support vs a hand rolled parser."
config file is supposed to be read/written by some built-in python library? what format and what library?

- should all the constants below go in the config file?

- why is it better to raise exceptions than to return an error value? it kills the program so the failure doesn't get reported to the user. or do you mean to catch all exceptions in upload() and return {success: false} from there?

- what do you mean by an external validator? i can separate validation into another object  but that still won't know things like what numbers correspond to an existing account.

- how can i remove all cherrypy dependency when the file parameter is a cherrypy object?
- how can i test the code that involves cherrypy stuff from the command line? i cannot pass in a cherrypy file object from a command-line interface (unless cherrypy provides a way to create it)

'''
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
# TODO: change this directory eventually
SAVE_DIRECTORY = '/tmp'

# format of error messages in the log file
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'


class BillUpload(object):

    def __init__(self):
        # read config file if it exists, to get path of log file
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
            config_file.close()

        # make sure log file is writable
        # TODO this should not even run if log_file was not assigned
        if not os.access(self.log_file, os.W_OK):
            # TODO what should happen in this case? (note that loging this
            # error is impossible)
            print 'log file path "%s" is not writable.' % log_file
            exit()
        
        # create logger
        self.logger = logging.getLogger('billupload')
        formatter = logging.Formatter(LOG_FORMAT)
        handler = logging.FileHandler(self.log_file)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler) 


    '''Accepts parameters for file upload, passes them to upload_bill, and
    returns a response in JSON format (because there shouldn't be any JSON mixed
    into the real code.)'''
    def upload(self, account, begin_date, end_date, file_to_upload):
        if self.upload_bill(account, begin_date, end_date, file_to_upload):
            return '{success: true}'
        return '{sucess: false}'

    '''Performs the actual work of uploading a file.'''
    def upload_bill(self, account, begin_date, end_date, file_to_upload):
        # check account name (removes malicious input, e.g. starting with '../')
        # TODO: check that it's really an existing account?
        if not re.match(ACCOUNT_NAME_REGEX, account):
            self.logger.error('invalid account name: "%s"' % account)
            # TODO raise exception? Perhaps an external validator can do this work since it
            # is not directly related to uploading and saving files
            return False
        
        # convert dates from string to python's 'time.struct_time' type, and
        # back, to get formatted dates
        try:
            begin_date_object = time.strptime(begin_date, INPUT_DATE_FORMAT)
            end_date_object = time.strptime(end_date, INPUT_DATE_FORMAT)
        except Exception as e:
            self.logger.error('unexpected date format(s): %s, %s\n%s' \
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
            self.logger.error('unable to read "' + file_to_upload.filename + '"')
            # TODO raise exception
            return False
        finally:
            file_to_upload.file.close()
        
        # path where file will be saved: # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
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
                self.logger.error('unable to create directory "%"' \
                        % os.path.join(SAVE_DIRECTORY, save_file_path));
                # TODO raise exception
                return False
        
        # write the file in SAVE_DIRECTORY
        save_file = open(save_file_path, 'w')
        try:
            save_file.write(data)
        except:
            self.logger.error('unable to write "' + save_file_path + '"')
            # TODO raise exception
            return False
        finally:
            save_file.close()

        return True

# command-line interface for testing
# note: this doesn't work because it passes argument 3 to upload_bill as a
# string, but it needs to be a cherrypy file object (<class 'cherrypy._cpreqbody.Part'>)
def main():
    bu = BillUpload()

    args = raw_input('> ').split()
    while args != ['q']:
        if len(args) == 4:
            print bu.upload(args[0], args[1], args[2], args[3])
        else:
            print 'enter 4 arguments'
        args = raw_input('> ').split()

if __name__ == '__main__':
    main()

