from billing import initialize
initialize()
from billing.http import make_flask_app

app = make_flask_app()

if __name__ == '__main__':
    import logging

    log = logging.getLogger(__name__)
    app.debug = True
    port = 5000
    host = '127.0.0.1'

    log.info('Serving on %s port %s' % (host, port))
    app.run(host=host, port=port)

