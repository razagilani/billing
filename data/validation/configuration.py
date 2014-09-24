"""Validation logic for the configuration file.
"""
from boto.s3.connection import OrdinaryCallingFormat, S3Connection
from formencode.schema import Schema
from formencode.validators import StringBool, String, URL, Int, Email, OneOf
from formencode.compound import All
from os.path import isdir
from formencode.api import FancyValidator, Invalid


class TCPPort(Int):
    min = 1
    max = 65535

class Directory(FancyValidator):
    def _convert_to_python(self, value, state):
        if isdir(value): return value
        raise Invalid("Please specify a valid directory", value, state)

class CallingFormat(FancyValidator):
    def _convert_to_python(self, value, state):
        if value == 'OrdinaryCallingFormat':
            return OrdinaryCallingFormat()
        elif value == 'DefaultCallingFormat':
            return S3Connection.DefaultCallingFormat
        raise Invalid('Please specify a valid calling format.')

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
    bucket = String()

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

class amqp(Schema):
    exchange = String()

class aws_s3(Schema):
    aws_access_key_id = String()
    aws_secret_access_key = String()
    host = String()
    port = TCPPort()
    is_secure = StringBool()
    calling_format = All(CallingFormat(),
                         OneOf(['OrdinaryCallingFormat',
                                'DefaultCallingFormat']))

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

