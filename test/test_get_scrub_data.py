from unittest import TestCase
from core import init_model, get_scrub_sql, get_scrub_columns
from core.model import Session
from reebill.reebill_model import ReeBillCustomer, ReeBill
from test import init_test_config


def setUpModule():
    init_test_config()
    init_model()

class TestGetScrubData(TestCase):
    """Test code for specifying which private information needs to be removed
    from a copy of a production database used for development.
    """
    def test_get_scrub_columns(self):
        """There has to be code that accesses the SQLAlchemy table/column
        objects because a plain SQL string could become outdated due to
        schema changes (which happened before).
        """
        # only keys matter because replacement values can be anything.
        # set is used to avoid requiring a specific order.
        expected = {ReeBillCustomer.__table__.c.bill_email_recipient,
                    ReeBill.__table__.c.email_recipient}
        self.assertEqual(expected, set(get_scrub_columns().keys()))

    def test_get_scrub_sql(self):
        # this is fragile because the SQL doesn't really have to come in one
        # \n-separated line per table (but splitting on ';' would be even
        # worse). if this test breaks and is hard to fix, the assertion could
        # be removed because test_get_scrub_columns checks the most important
        # part.
        expected_lines = {
            ("update reebill_customer set bill_email_recipient = "
            "'example@example.com' where bill_email_recipient is not null;"),
            ("update reebill set email_recipient = 'example@example.com' where "
            "email_recipient is not null;")}
        sql = get_scrub_sql()
        actual_lines = set(sql.split('\n'))
        self.assertEqual(expected_lines, actual_lines)

        # validate by executing on an empty database.
        # (it should not be necessary to clear the database before/after this)
        Session().execute(get_scrub_sql())
