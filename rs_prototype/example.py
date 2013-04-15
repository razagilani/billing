'''Example code using the new rate structure classes in rs_prototype.py'''
from datetime import datetime
import mongoengine
from mongoengine import Document, EmbeddedDocument, ListField, StringField, FloatField, IntField, DictField, EmbeddedDocumentField, ReferenceField
from math import floor, ceil
import pymongo
from rs_prototype import TimeDependentValue, StartBasedTDV, ProratedTDV, RSI, URS, SoCalRS, Process

mongoengine.connect('temp')

# based on 10031-7-1
socalrs_instance = SoCalRS(
    name='GM-E Residential',

    # inputs that change monthly (with utility bill periods mapped to calendar
    # periods using the "start" rule). these use the complicated "prorate"
    # mapping rule, meaning that the value that actually gets used in a given
    # bill is usually not any of the specific values below.
    under_baseline_rate = ProratedTDV(
        date_value_pairs= [
            [datetime(2012,10,1), 0.7282],
            [datetime(2012,11,1), 0.7282],
            [datetime(2012,12,1), 0.7282],
        ],
    ),
    over_baseline_rate = ProratedTDV(
        date_value_pairs= [
            [datetime(2012,10,1), 0.9782],
            [datetime(2012,11,1), 0.9782],
            [datetime(2012,12,1), 0.9782],
        ],
    ),

    # inputs that have never changed so far, but may change in the future. the
    # initial value extends indefinitely into the future until a new value is
    # added with a later date.
    customer_charge_rate=StartBasedTDV(
        date_value_pairs=[
            [datetime(2010,1,1), .16438],
        ],
    ),
    state_regulatory_rate=StartBasedTDV(
        date_value_pairs=[
            [datetime(2010,1,1), .00068],
        ],
    ),
    public_purpose_rate=StartBasedTDV(
        date_value_pairs=[
            [datetime(2010,1,1), .08231],
        ],
    ),

    # these inputs are constant. should we treat all inputs as possibly
    # time-dependent even if they're not expected to change? if mapping rules
    # never change, we might be able to assume that some actual values never
    # change either.
    summer_allowance = StartBasedTDV(
        date_value_pairs=[
            [datetime(2010,1,1), 2]
        ]
    ),
    winter_allowance = StartBasedTDV(
        date_value_pairs=[
            [datetime(2010,1,1), 3]
        ]
    ),
    summer_start_month = 4,
    winter_start_month = 10,

    # RSI formulas, named with underscore to distinguish from symbol names
    # (TODO maybe these move somewhere else? or find some other way of
    # distinguishing them from the inputs?)
    _rsis = {
        'Gas Service Baseline': # over basline
            RSI(formula=('over_baseline_rate * Max(0, total_register - num_units *'
            '(winter_allowance * days_in_winter + summer_allowance * '
            'days_in_summer))'), round_rule='down'),
        'Gas Service Non Baseline': # under baseline
            RSI(formula=('under_baseline_rate * Min(total_register, num_units * '
            '(winter_allowance * days_in_winter + summer_allowance * '
            'days_in_summer))'), round_rule='down'),
        'Customer Charge': RSI(formula='customer_charge_rate * num_units'),
        'State Regulatory': RSI(formula='state_regulatory_rate * total_register'),
        'Public Purpose': RSI(formula='public_purpose_rate * total_register'),

        # taxes combined with other charges because we believe nothing is to be
        # gained by separating them (according to Rich, customers in same
        # jurisdiction with different suppliers/distributors do NOT pay the
        # same taxes)
        # TODO how can charges depend on other charges? should they appear as
        # symbols in the formula? is there a good way to apply a tax to all
        # other charges "of a certain type" in the same URS?
        #'LA City Users': RSI(formula='.01 * ...'),
    }
)

#la_tax_rs = TaxRS(
#    name = 'LA taxes',
#    other_rss=[socalrs_instance],
#    _rsis={
#        'LA City Users': RSI(formula='.1 * all_non_tax')
#    }
#)

# clear db and save the 2 documents in it
pymongo.Connection('localhost')['temp']['urs'].drop()
socalrs_instance.save()
#la_tax_rs.save()
socalrs_instance = URS.objects.get(name='GM-E Residential')

# we should be using a class for utility bills (see branch utilbill-class) but
# we are currently using raw dictionaries (with more data than this in them)
utilbill_doc = {
    # based on 10031-7
    'registers': {
        'total_register': {'quantity': 440},
    },
    'start': datetime(2012,11,20),
    'end': datetime(2012,12,20),

    # data that the Sempra Energy rate structure requires that others do not
    # require: building size in units
    'num_units': 30,
}

#for name in ['Gas Service Under Baseline', 'Gas Service Over Baseline', 'Customer Charge']:
for rs in (socalrs_instance, ):
    for charge_name in sorted(rs._rsis.keys()):
        print '%50s: %6s' % (rs.name + '/' + charge_name,
                '%.2f' % Process().compute_charge(rs, charge_name, utilbill_doc))

pymongo.Connection('localhost')['temp']['urs'].drop()
