"""Read and parse and email with a matrix quote spreadsheet attachment from
stdin. Can be triggered by Postfix.
"""
from sys import stdin
from cStringIO import StringIO
from brokerage.read_quotes import DirectEnergyMatrixParser
from util.email_util import get_attachments

if __name__ == '__main__':
    email_text = stdin.read()
    attachments = get_attachments(email_text)
    assert len(attachments) == 1
    name, content = attachments[0]
    quote_file = StringIO()
    quote_file.write(content)
    quote_file.seek(0)

    quote_parser = DirectEnergyMatrixParser()
    quote_parser.load_file(quote_file)
    quote_parser.validate()

    for q in quote_parser.extract_quotes():
        print q
