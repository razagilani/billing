"""Receive quotes from suppliers' "matrix" spreadsheets (files from a Dropbox
directory or email attachments).
"""
from brokerage.quote_file_processor import QuoteFileProcessor
from core import initialize

if __name__ == '__main__':
    initialize()
    QuoteFileProcessor().run()
