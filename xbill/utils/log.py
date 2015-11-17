from logging.handlers import RotatingFileHandler
from xbill.settings import LOGGING_DIR_PATH

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_client_id(request):
    if request.user.is_authenticated():
        return "[%s] %s " % (get_client_ip(request),request.user.email_address)
    else:
        return "[%s] " % get_client_ip(request)


class CustomRotatingFileHandler(RotatingFileHandler):

    def __init__(self, filename, mode, bytes):
        super(CustomRotatingFileHandler, self).__init__(
           LOGGING_DIR_PATH+filename, mode, bytes
        )