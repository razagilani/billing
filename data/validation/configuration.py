"""Validation logic for the configuration file.
"""

from formencode.schema import Schema
from formencode.validators import StringBool, String, URL, Int, Email
from os.path import isdir
from formencode.api import FancyValidator, Invalid

class TCPPort(Int):
    min = 1
    max = 65535

class Directory(FancyValidator):
    def _convert_to_python(self, value, state):
        if isdir(value): return value
        raise Invalid("Please specify a valid directory", value, state)        

class alembic(Schema):
    script_location = Directory()

class runtime(Schema):
    integrate_skyline_backend = StringBool()
    integrate_nexus = StringBool()
    sessions_key = String()
    mock_skyliner = StringBool()
    
class skyline_backend(Schema):    
    oltp_url = URL()
    olap_host = String()
    olap_database = String()
    nexus_db_host = String()
    nexus_web_host = String()

class journaldb(Schema):
    host = String()
    port = TCPPort()
    database = String()
    
class http(Schema):
    socket_port = TCPPort()
    socket_host = String()
    
class rsdb(Schema):
    host = String()
    port = TCPPort(min=1, max=65535)
    database = String()
    
class billdb(Schema):
    utilitybillpath = String()
    billpath = String()
    host = String()
    port = TCPPort(min=1, max=65535)
    database = String()
    utility_bill_trash_directory = String()
    
class statedb(Schema):
    uri = String()
    echo = StringBool()
    
class usersdb(Schema):
    host = String()
    database = String()
    port = TCPPort()
    
class mailer(Schema):
    smtp_host = String()
    smtp_port = TCPPort()
    originator = Email()
    mail_from = String()
    bcc_list = String()
    password = String()
    
class authentication(Schema):
    authenticate = StringBool()
    
class billimages(Schema):
    bill_image_directory = String()
    show_reebill_images = StringBool()
    
class reebillrendering(Schema):
    temp_directory = Directory()
    template_directory = Directory()
    default_template = String()
    teva_accounts = String()
    
class reebillreconciliation(Schema):
    log_directory = Directory()
    report_directory = Directory()
    
class reebillestimatedrevenue(Schema):
    log_directory = Directory()
    report_directory = Directory()

    

    
    