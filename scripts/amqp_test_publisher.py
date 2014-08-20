from billing.lib.amqp import ExchangePublisher

xp = ExchangePublisher('mikes_exchange')

xp.publish('handler_key', {'message': 'hello!'})
xp.publish('other_handler', {'message': 'other_message'})