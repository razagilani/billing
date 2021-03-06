from StringIO import StringIO
from jinja2 import Template
from mock import Mock, call

from test import init_test_config

def setUpModule():
    init_test_config()

from unittest import TestCase
from reebill.bill_mailer import Mailer

class BillMailerTest(TestCase):
    def setUp(self):
        pass

    def test_send_mail(self):
        from core import config
        server = Mock()
        mailer_opts = dict(config.items("mailer"))
        bill_mailer = Mailer(
                mailer_opts['mail_from'],
                mailer_opts['originator'],
                mailer_opts['password'],
                server,
                mailer_opts['smtp_host'],
                mailer_opts['smtp_port'],
                mailer_opts['bcc_list']
        )

        content = "mail body content"
        subject = "Subject"

        bill_mailer.mail('one@example.com, one@gmail.com', subject, content,
                         StringIO('data').read(), 'text.txt', boundary='abc')
        contents1 = []
        # TODO don't use repeated hardcoded file paths and don't use relative
        # file paths
        contents1.append('Content-Type: multipart/mixed; boundary="abc"\n')
        contents1.append(('MIME-Version: 1.0\n'))
        contents1.append('Subject: Subject\n')
        contents1.append('From: "Skyline Billing (Dev)" <energy_billing@skylineinnovations.com>\n')
        contents1.append('To: one@example.com, one@gmail.com\n')
        contents1.append('\n')
        contents1.append('--abc\n')
        contents1.append('Content-Type: text/plain; charset="us-ascii"\n')
        contents1.append('MIME-Version: 1.0\n')
        contents1.append('Content-Transfer-Encoding: 7bit\n')
        contents1.append('Content-Disposition: attachment; filename="text.txt"\n')
        contents1.append('\n')
        contents1.append('data')
        contents1.append('\n')
        contents1.append('--abc\n')
        contents1.append('Content-Type: text/html; charset="us-ascii"\n')
        contents1.append('MIME-Version: 1.0\n')
        contents1.append('Content-Transfer-Encoding: 7bit\n')
        contents1.append('\n')
        contents1.append(content)
        contents1.append('\n--abc--\n')

        contents2 = []
        # TODO don't use repeated hardcoded file paths and don't use relative
        # file paths
        contents2.append('Content-Type: multipart/mixed; boundary="abc"\n')
        contents2.append(('MIME-Version: 1.0\n'))
        contents2.append('Subject: Nextility: Your Monthly Bill for 456 test Ave.\n')
        contents2.append('From: "Skyline Billing (Dev)" <energy_billing@skylineinnovations.com>\n')
        contents2.append('To: one@example.com, one@gmail.com\n')
        contents2.append('Bcc: someone@example.com, others@gmail.com\n')
        contents2.append('\n')
        contents2.append('--abc\n')
        contents2.append('Content-Type: text/plain; charset="us-ascii"\n')
        contents2.append('MIME-Version: 1.0\n')
        contents2.append('Content-Transfer-Encoding: 7bit\n')
        contents2.append('Content-Disposition: attachment; filename="text.txt"\n')
        contents2.append('\n')
        contents2.append('data')
        contents2.append('\n')
        contents2.append('--abc\n')
        contents2.append('Content-Type: text/html; charset="us-ascii"\n')
        contents2.append('MIME-Version: 1.0\n')
        contents2.append('Content-Transfer-Encoding: 7bit\n')
        contents2.append('\n')
        contents2.append(content)
        contents2.append('\n--abc--\n')
        server.ehlo.assert_has_calls([call(), call()])
        server.starttls.assert_has_calls([call()])
        server.login.assert_has_calls([call(mailer_opts['originator'], mailer_opts['password'])])
        calls = [call(mailer_opts['originator'], ['one@example.com', 'one@gmail.com'], ''.join(contents1)),
                call(mailer_opts['originator'], ['someone@example.com', 'others@gmail.com'], ''.join(contents2))]
        server.sendmail.asserrt_has_calls(calls)
        # TODO don't use repeated hardcoded file paths and don't use relative
        # file paths
        # TODO don't use repeated hardcoded file paths and don't use relative
        # file paths
        recipient = 'one@example.com, one@gmail.com'
        bill_mailer.mail(recipient, subject, content, StringIO('data').read(),
                         'utility_bill.pdf', boundary='abc')
        bill_mailer.mail(recipient, subject, content, StringIO('data').read(),
                         'audio.wav', boundary='abc')
        bill_mailer.mail(recipient, subject, content,
                         StringIO('data').read(), 'image.jpg', boundary='abc' )
        bill_mailer.mail(recipient, subject, content,
                         StringIO('data').read(), 'video.mov', boundary='abc' )
        server.ehlo.assert_has_calls([call(), call(), call(), call(), call(), call()])
        server.starttls.asserrt_has_calls([call(), call(), call(), call()])
        server.login.assert_has_calls([call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password'])])

        #server.send_mail.assert_called_once_with('energy_billing@skylineinnovations.com', ['one@example.com', 'one@gmail.com'], email_data)


