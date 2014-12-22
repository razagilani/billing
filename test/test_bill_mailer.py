from jinja2 import Template
from test import init_test_config
init_test_config()

from mock import Mock, call

from unittest import TestCase
from reebill.bill_mailer import Mailer, TEMPLATE_FILE_PATH

class BillMailerTest(TestCase):
    def setUp(self):
        with open(TEMPLATE_FILE_PATH) as template_file:
            self.template_html = template_file.read()

    def test_send_mail(self):
        from core import config
        from test import init_test_config
        init_test_config()
        server = Mock()
        #server.send_mail = Mock()
        mailer_opts = dict(config.items("mailer"))
        bill_mailer = Mailer(
                mailer_opts['mail_from'],
                mailer_opts['originator'],
                mailer_opts['password'],
                mailer_opts['template_file_name'],
                server,
                mailer_opts['smtp_host'],
                mailer_opts['smtp_port'],
                mailer_opts['bcc_list']
        )
        merge_fields = {
            'street': '456 test Ave.',
            'balance_due': 20
        }
        # TODO: use of repeated hardcoded file path is bad
        bill_mailer.mail(['one@example.com', 'one@gmail.com'], merge_fields,
                         'test/test_core/data', ['text.txt'], boundary='abc' )
        contents1 = []
        # TODO: use of repeated hardcoded file path is bad
        data = open('test/test_core/data/text.txt', 'r').read()
        contents1.append('Content-Type: multipart/mixed; boundary="abc"\n')
        contents1.append(('MIME-Version: 1.0\n'))
        contents1.append('Subject: Nextility: Your Monthly Bill for 456 test Ave.\n')
        contents1.append('From: "Skyline Billing (Dev)" <energy_billing@skylineinnovations.com>\n')
        contents1.append('To: one@example.com, one@gmail.com\n')
        contents1.append('\n')
        contents1.append('--abc\n')
        contents1.append('Content-Type: text/plain; charset="us-ascii"\n')
        contents1.append('MIME-Version: 1.0\n')
        contents1.append('Content-Transfer-Encoding: 7bit\n')
        contents1.append('Content-Disposition: attachment; filename="text.txt"\n')
        contents1.append('\n')
        contents1.append(data)
        contents1.append('\n')
        contents1.append('--abc\n')
        contents1.append('Content-Type: text/html; charset="us-ascii"\n')
        contents1.append('MIME-Version: 1.0\n')
        contents1.append('Content-Transfer-Encoding: 7bit\n')
        contents1.append('\n')
        html = Template(self.template_html).render(merge_fields)
        contents1.append(html)
        contents1.append('\n--abc--\n')

        contents2 = []
        # TODO: use of repeated hardcoded file path is bad
        data = open('test/test_core/data/text.txt', 'r').read()
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
        contents2.append(data)
        contents2.append('\n')
        contents2.append('--abc\n')
        contents2.append('Content-Type: text/html; charset="us-ascii"\n')
        contents2.append('MIME-Version: 1.0\n')
        contents2.append('Content-Transfer-Encoding: 7bit\n')
        contents2.append('\n')
        html = Template(self.template_html).render(merge_fields)
        contents2.append(html)
        contents2.append('\n--abc--\n')
        server.ehlo.assert_has_calls([call(), call()])
        server.starttls.asserrt_has_calls([call()])
        server.login.assert_has_calls([call(mailer_opts['originator'], mailer_opts['password'])])
        calls = [call(mailer_opts['originator'], ['one@example.com', 'one@gmail.com'], ''.join(contents1)),
                call(mailer_opts['originator'], ['someone@example.com', 'others@gmail.com'], ''.join(contents2))]
        server.sendmail.assert_has_calls(calls)
        # TODO: use of repeated hardcoded file path is bad
        bill_mailer.mail(['one@example.com', 'one@gmail.com'], merge_fields,
                         'test/test_core/data', ['utility_bill.pdf'],
                         boundary='abc' )
        bill_mailer.mail(['one@example.com', 'one@gmail.com'], merge_fields,
                         'test/test_core/data', ['audio.wav'], boundary='abc' )
        bill_mailer.mail(['one@example.com', 'one@gmail.com'], merge_fields,
                         'test/test_core/data', ['image.jpg'], boundary='abc' )
        bill_mailer.mail(['one@example.com', 'one@gmail.com'], merge_fields,
                         'test/test_core/data', ['video.mov'], boundary='abc' )
        server.ehlo.assert_has_calls([call(), call(), call(), call(), call(), call()])
        server.starttls.asserrt_has_calls([call(), call(), call(), call()])
        server.login.assert_has_calls([call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password']),
            call(mailer_opts['originator'], mailer_opts['password'])])

        #server.send_mail.assert_called_once_with('energy_billing@skylineinnovations.com', ['one@example.com', 'one@gmail.com'], email_data)


