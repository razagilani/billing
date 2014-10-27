from billing.lib.amqp import ExchangeListener

def handler_key(message):
    print 'whee got message: %s' % message

def other_handler(message):
    print 'got message from other handler: %s' % message

xl = ExchangeListener('mikes_exchange', handlers=[handler_key, other_handler])
xl.listen()

