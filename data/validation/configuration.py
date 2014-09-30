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

class runtime(Schema):
    integrate_nexus = StringBool()
    sessions_key = String()
    mock_skyliner = StringBool()
    
class skyline_backend(Schema):    
    oltp_url = URL()
    olap_host = String()
    olap_database = String()
    nexus_db_host = String()
    nexus_web_host = String()
    nexus_offline_cache_file = String()

class http(Schema):
    socket_port = TCPPort()
    socket_host = String()
    
class bill(Schema):
    utilitybillpath = String()
    billpath = String()
    utility_bill_trash_directory = String()

class statedb(Schema):
    uri = String()
    echo = StringBool()

class mongodb(Schema):
    database = String()
    host = String()
    port = TCPPort()

class mailer(Schema):
    smtp_host = String()
    smtp_port = TCPPort()
    originator = Email()
    mail_from = String()
    bcc_list = String()
    password = String()
    template_file_name = String()
    
class authentication(Schema):
    authenticate = StringBool()
    
class reebillrendering(Schema):
    template_directory = Directory()
    default_template = String()
    teva_accounts = String()
    
class reebillreconciliation(Schema):
    log_directory = Directory()
    report_directory = Directory()
    
class reebillestimatedrevenue(Schema):
    log_directory = Directory()
    report_directory = Directory()

#Logging

class loggers(Schema):
    keys = String()

class handlers(Schema):
    keys = String()

class formatters(Schema):
    keys = String()

class logger_root(Schema):
    level = String()
    handlers = String()

class logger_sqlalchemy(Schema):
    level = String()
    handlers = String()
    qualname = String()

class logger_reebill(Schema):
    level = String()
    handlers = String()
    qualname = String()
    propagate = Int()

class handler_consoleHandler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_consoleHandler.add_field('class', String())

class handler_reebillHandler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_reebillHandler.add_field('class', String())

class handler_fileHandler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_fileHandler.add_field('class', String())

class formatter_simpleFormatter(Schema):
    format = String()

