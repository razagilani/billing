from datetime import datetime
from flask_wtf import Form
from wtforms import SelectField
from wtforms.fields.simple import TextField, TextAreaField
from wtforms.validators import DataRequired, ValidationError, InputRequired
from billing.data.model import UsePeriod

##Field Validators
def validate_use_periods(form, field):

    for csv_row in field.data.split("\n"):
        UsePeriod.from_csv_row(csv_row)

def tstvalidate(form, field):
    raise ValidationError('error')
    print field.raw_data


##Forms
class InterestNew(Form):
    customers = SelectField('Category', choices=[], coerce=int)


class InterestEdit(Form):
    name = TextField('Customer Name', validators=[InputRequired()])
    street = TextField('Street', validators=[InputRequired()])
    city = TextField('City', validators=[InputRequired()])
    state = TextField('State', validators=[InputRequired()])
    postal_code = TextField('Postal Code', validators=[InputRequired()])

    rate_class = SelectField('Rate Class', choices=[], coerce=int,
                             validators=[DataRequired()])

    use_periods = TextAreaField('Use Periods',
                                validators=[validate_use_periods])


class TestForm(Form):
    name = TextField('name', validators=[DataRequired()])
