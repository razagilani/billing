from django.contrib.messages.api import get_messages
from xbill import settings


def sort_messages(request):
    messages = get_messages(request)
    info_messages = []
    success_messages = []
    warning_messages = []
    error_messages = []
    for m in messages:
        if 'info' in m.tags:
            info_messages.append(m)
        if 'success' in m.tags:
            success_messages.append(m)
        if 'warning' in m.tags:
            warning_messages.append(m)
        if 'error' in m.tags:
            error_messages.append(m)
    return {'errormsgs': error_messages,
            'warningmsgs': warning_messages,
            'infomsgs': info_messages,
            'successmsgs': success_messages, }
