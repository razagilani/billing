"""Read and parse and email with a matrix quote spreadsheet attachment from
stdin. Can be triggered by Postfix.
"""
# TODO: move code other than __main__ out of this file into a new file in
# "brokerage", and add tests for it
from brokerage.quote_file_processor import QuoteFileProcessor
from core import init_altitude_db, init_config, init_logging, init_model


if __name__ == '__main__':
    init_config()
    # TODO: this causes confusing duplicate output from SQLAlchemy when "echo" is turned on. re-enable later
    init_logging()
    init_altitude_db()
    init_model()

    QuoteFileProcessor().run()
