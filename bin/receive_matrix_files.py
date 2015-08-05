"""Receive quotes from suppliers' "matrix" spreadsheets (files from a Dropbox
directory or email attachments).
"""
from sys import stdin
from brokerage.quote_file_processor import QuoteEmailProcessor
from core import initialize

if __name__ == '__main__':
    initialize()
    QuoteEmailProcessor().process_email(stdin)
