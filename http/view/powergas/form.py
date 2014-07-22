from datetime import datetime
from flask_wtf import Form
from wtforms import SelectField
from wtforms.fields.core import StringField, IntegerField, BooleanField
from wtforms.fields.simple import TextField, TextAreaField
from wtforms.validators import DataRequired, ValidationError, InputRequired, \
    Optional
from billing.data.model import UsePeriod, Session, RateClass, Company


def validate_use_periods(form, field):
    dt = lambda x: datetime.strptime(x.strip(), "%Y-%m-%d")
    try:
        for csv_row in field.data.split("\n"):
            start, end, q = csv_row.split(",")
            dt(start), dt(end), float(q)
    except Exception:
        raise ValidationError("Please input as YYYY-MM-DD, YYYY-MM-DD, XX.XX")


def tstvalidate(form, field):
    raise ValidationError('error')
    print field.raw_data


##Forms
class InterestNew(Form):
    customers = SelectField('Category', choices=[], coerce=int)


class InterestEditForm(Form):
    name = TextField('Customer Name', validators=[InputRequired()])
    street = TextField('Street', validators=[InputRequired()])
    city = TextField('City', validators=[InputRequired()])
    state = TextField('State', validators=[InputRequired()])
    postal_code = TextField('Postal Code', validators=[InputRequired()])
    rate_class = SelectField('Rate Class', choices=[], coerce=int,
                             validators=[DataRequired()])

    use_periods = TextAreaField('Use Periods',
                                validators=[validate_use_periods])

    @staticmethod
    def rate_class_choices():
        s = Session()
        return [(r.id, "%s - %s" % (r.utility.name, r.name))
                for r in s.query(RateClass).all()]

    def __init__(self, *args, **kwargs):
        """Construct a new :class:`.InterestEdit` form"""
        super(InterestEditForm, self).__init__(*args, **kwargs)
        self.rate_class.choices = InterestEditForm.rate_class_choices()

class TestForm(Form):
    name = TextField('name', [DataRequired()])

class QuoteForm(Form):

    rate_class = SelectField('Rate Class', [Optional()], choices=[], coerce=int)
    company = SelectField('Company', [Optional()], choices=[], coerce=int)
    offset = IntegerField('Offset', [Optional()], default=0)
    include_expired = BooleanField('Include Expired', [Optional()],
                                   default=False)

    @staticmethod
    def company_choices():
        s = Session()
        return [(c.id, c.name) for c in s.query(Company).all()]

    def __init__(self, *args, **kwargs):
        super(QuoteForm, self).__init__(*args, **kwargs)
        self.rate_class.choices = InterestEditForm.rate_class_choices()
        self.company.choices = QuoteForm.company_choices()
