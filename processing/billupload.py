import os
import errno
import logging
import time
import re
import cherrypy
from cherrypy.lib import static

CONFIG_FILE = 'billupload_config'

# strings allowed as account names
ACCOUNT_NAME_REGEX = '[0-9]{5}'

# date format expected from front end
INPUT_DATE_FORMAT ='%Y-%m-%d' 

# date format that goes in names of saved files
OUTPUT_DATE_FORMAT = '%Y%m%d'

# where account directories are located (uploaded files are saved inside of
# those)
SAVE_DIRECTORY = '/tmp'

# format of error messages in the log file
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'


# read log file path from config file
for index, line in enumerate(open(CONFIG_FILE).read().split('\n')):
    if index == 0:
        log_file = line

# create logger
logger = logging.getLogger('billupload')
formatter = logging.Formatter(LOG_FORMAT)
handler = logging.FileHandler(log_file)
handler.setFormatter(formatter)
logger.addHandler(handler) 


class BillUpload(object):
        
    @cherrypy.expose
    # **args catches any extra parameters (ignored)
    def upload(self, account, begin_date, end_date, file_to_upload, **args):
        # check account name (removes malicious input, e.g. starting with '../')
        # TODO: check that it's really an existing account?
        if not re.match(ACCOUNT_NAME_REGEX, account):
            logger.error('invalid account name: "%s"' % account)
            return '{success: false}'
        
        # convert dates from string to python's 'time.struct_time' type, and back,
        # to get formatted dates
        try:
            begin_date_object = time.strptime(begin_date, INPUT_DATE_FORMAT)
            end_date_object = time.strptime(end_date, INPUT_DATE_FORMAT)
        except:
            logger.error('unexpected date format(s): %s, %s' \
                    % (begin_date, end_date))
            return '{success: false}'
        formatted_begin_date = time.strftime(OUTPUT_DATE_FORMAT, begin_date_object)
        formatted_end_date = time.strftime(OUTPUT_DATE_FORMAT, end_date_object)
        
        # read whole file in one chunk
        try:
            data = file_to_upload.file.read()
        except:
            logger.error('unable to read "' + file_to_upload.filename + '"')
            return '{success: false}'
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
                return '{success: false}'
        
        # write the file in SAVE_DIRECTORY
        save_file = open(save_file_path, 'w')
        try:
            save_file.write(data)
        except:
            logger.error('unable to write "' + save_file_path + '"')
            return '{success: false}'
        finally:
            save_file.close()

        return '{success: true}'

# configuration
local_conf = {
    '/' : {
        'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
        'tools.staticdir.dir' : '',
        'tools.staticdir.on' : True,
        'tools.expires.secs': 0,
        'tools.response_headers.on': True,
    },
    '/js' :  {
        'tools.staticdir.dir' : 'js',
        'tools.staticdir.on' : True 
    },
}
cherrypy.config.update({
    #'server.socket_host': "10.0.0.250",
    'server.socket_port': 8080,
})

cherrypy.quickstart(BillUpload(), config=local_conf)
