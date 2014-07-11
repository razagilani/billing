from flask_wtf import Form
from wtforms import SelectField

class CustomerInterestForm(Form):
    customers = SelectField('Category', choices=[], coerce=int)