"""Validation logic for the configuration file.
TODO: find someplace to put this other than the root directory.
"""
from boto.s3.connection import OrdinaryCallingFormat, S3Connection
from formencode.exc import FERuntimeWarning
from formencode.schema import Schema
from formencode.validators import (StringBool, String, URL, Int, Number, Email,
                                   OneOf, Empty)
from formencode.compound import All, Any
from os.path import isdir
from formencode.api import FancyValidator, Invalid


class InvalidDirectoryPath(Invalid):
    '''Special exception for directory paths, because errors about these are
    ignored when validating config files meant for deployment on a different
    host.
    '''

class TCPPort(Int):
    min = 1
    max = 65535

# class Directory(FancyValidator):
#     def _convert_to_python(self, value, state):
#         if isdir(value): return value
#         raise InvalidDirectoryPath("Please specify a valid directory",
#                                    value, state)
class Directory(String):
    # existence of directory paths has to be ignored in order to check
    # validity of a config file while not running on the host where those
    # directories exist.
    # also note that it is not possible to use a custom subclass of
    # Invalid because formencode will catch it and re-raise Invalid.
    pass

class CallingFormat(FancyValidator):
    def _convert_to_python(self, value, state):
        if value == 'OrdinaryCallingFormat':
            return OrdinaryCallingFormat()
        elif value == 'DefaultCallingFormat':
            return S3Connection.DefaultCallingFormat
        raise Invalid('Please specify a valid calling format.')

class reebill(Schema):
    # host and port for running ReeBill web app with built-in server
    socket_port = TCPPort()
    socket_host = String()

    # whether users must log in
    authenticate = StringBool()
    sessions_key = String()

    # databases for getting renewable energy data
    oltp_url = URL()
    olap_host = String()
    olap_database = String()
    mock_skyliner = StringBool()

    # ways to access the database of alternate customer names
    nexus_db_host = String()
    nexus_web_host = String()
    nexus_offline_cache_file = String()
    reebill_file_path = Directory()

    # account numbers for bills whose PDFs are rendered using the "teva" format
    teva_accounts = String()

class reebillreconciliation(Schema):
    log_directory = Directory()
    report_directory = Directory()

class billentry(Schema):
    google_client_id = String()
    google_client_secret = String()
    google_user_info_url = URL()
    redirect_uri = String()
    base_url = URL()
    authorize_url = URL()
    request_token_url = URL()
    request_token_params_scope = String()
    request_token_params_resp_type = String()
    access_token_url = URL()
    access_token_method = String()
    access_token_params_grant_type = String()
    disable_authentication = StringBool()
    authorized_domain = String()
    show_traceback_on_error = StringBool()
    secret_key = String()
    wiki_url = String()

class reebillestimatedrevenue(Schema):
    log_directory = Directory()
    report_directory = Directory()

class db(Schema):
    # MySQL database
    uri = String()
    echo = StringBool()

class mongodb(Schema):
    database = String()
    host = String()
    port = TCPPort()

class mailer(Schema):
    # sending reebill emails to customers
    smtp_host = String()
    smtp_port = TCPPort()
    originator = Email()
    mail_from = String()
    bcc_list = String()
    password = String()
    
class amqp(Schema):
    # parameters for receiving utility bills via AMQP--should be named something
    # more specific if additional AMQP stuff needs to go in this file
    url = String()
    exchange = String()
    utilbill_routing_key = String()
    utilbill_guids_routing_key = String()

class aws_s3(Schema):
    # utility bill file storage in Amazon S3
    bucket = String()
    aws_access_key_id = String()
    aws_secret_access_key = String()
    host = String()
    port = TCPPort()
    is_secure = StringBool()
    calling_format = All(CallingFormat(),
                         OneOf(['OrdinaryCallingFormat',
                                'DefaultCallingFormat']))
    # optional settings for boto HTTP requests
    # note: empty values get converted to None
    num_retries = Any(validators=[Number(), Empty()])
    max_retry_delay = Any(validators=[Number(), Empty()])
    http_socket_timeout = Any(validators=[Number(), Empty()])

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

class logger_billentry(Schema):
    level = String()
    handlers = String()
    qualname = String()
    propagate = Int()

class logger_amqp_utilbill_file(Schema):
    level = String()
    handlers = String()
    qualname = String()

class logger_amqp_utilbill_guids_file(Schema):
    level = String()
    handlers = String()
    qualname = String()

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

class handler_billentry_file_handler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_billentry_file_handler.add_field('class', String())

class handler_amqp_utilbill_file_handler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_amqp_utilbill_file_handler.add_field('class', String())

class handler_amqp_utilbill_guids_file_handler(Schema):
    level = String()
    formatter = String()
    args = String()
handler_amqp_utilbill_guids_file_handler.add_field('class', String())

class formatter_simpleFormatter(Schema):
    format = String()

