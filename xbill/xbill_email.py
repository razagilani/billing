import os
from billing.util.email_util import send_email

# TODO customize these
TEMPLATE_FILE_NAME = 'hypothetical_savings_email.html'
FROM_USER = 'X. Bill'
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
ORIGINATOR = 'reports@skylineinnovations.com'
PASSWORD = 'electricsh33p'

def send_hypothetical_savings_email(recipients, utility, actual_dollars,
        minimal_dollars, energy, contact_email):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ui',
            TEMPLATE_FILE_NAME)) as template_file:
        template = template_file.read()
        values = {
            'energy': energy,
            'actual_dollars': actual_dollars,
            'minimal_dollars': minimal_dollars,
            'contact_email': contact_email,
            'utility': utility,
        }
        send_email(FROM_USER, recipients,
                'Save $%s on your electricity bill' % (actual_dollars - minimal_dollars),
                ORIGINATOR, PASSWORD, SMTP_HOST, SMTP_PORT, template, values)


if __name__ == '__main__':
    # example
    send_hypothetical_savings_email(['dklothe@skylineinnovations.com'], 'Pepco', 150, 100, 10, 'tech@skylineinnovations.com')
