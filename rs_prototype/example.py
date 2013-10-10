'''Example code using the new rate structure classes in rs_prototype.py'''
from datetime import datetime
import mongoengine
from mongoengine import Document, EmbeddedDocument, ListField, StringField, FloatField, IntField, DictField, EmbeddedDocumentField, ReferenceField
from math import floor, ceil
import pymongo
from rs_prototype import TimeDependentValue, StartBasedTDV, ProratedTDV, RSI, URS, SoCalRS, Process, WGDeliveryInterruptDC, GasSupplyContract

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
socalrs_instance.save(safe=True, force_insert=True)
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
        print '%50s: %8s' % (rs.name + ' - ' + charge_name,
                '%.2f' % Process().compute_charge(rs, charge_name, utilbill_doc))











# 10022-12 

wg_10022 = WGDeliveryInterruptDC(
    system_charge = 63.55,
    distribution_rate = StartBasedTDV(
        date_value_pairs=[
            [datetime(2012,1,1), .1721]
        ]
    ),
    balancing_rate = StartBasedTDV(
        date_value_pairs=[
            [datetime(2012,1,1), .002]
        ]
    ),
    dc_rights_of_way_fee = 484.95,
    sustainable_energy_trust_fund = 192.88,
    energy_assistance_trust_fund = 82.66,
    delivery_tax_rate = .0707,

    dc_sales_tax_rate = .06, # shown on the supplier (Hess) part of the bill!
)

hess_10022 = GasSupplyContract(
    # NOTE all energy quantities are in MMBTU, not therms

    deal_id = '1308690',

    start = datetime(2012,1,1),
    # real bill says 2012-12-31, probably meaning 2013-01-01 exclusive end date;w
    end = datetime(2013,1,1),

    contract_volume = 1271,

    # bill suggests there is no "allowed" range of deviation within which you
    # sell back unused energy at the same rate you can buy it at ('normal_rate')
    low_swing = 0,
    high_swing = 0,

    # sell-back rate
    low_penalty_rate = 0, # TODO unknown--must get it from the contract itself
    # " Contract Volume" unit price and "Swing Volume [0%]" unit price are the same
    normal_rate = 5.251,
    high_penalty_rate = 4.264166,

    _rsis = {
        'Contract Volume': RSI(formula=('contract_volume * normal_rate')),
        'Swing Volume [0%]': RSI(formula=('Max(0, high_swing - (total_register - contract_volume)) * normal_rate + Max(0, (contract_volume - total_register) - low_swing) * normal_rate')),

        # GSA Volume = under-consumption OR over-consumption: buy more at
        # high_penalty_rate or sell back at low_penalty_rate (either 1st term
        # or 2nd term will be non-0 but not both)
        'GSA Volume': RSI(formula=(('Max(0, total_register - contract_volume)'
                '* high_penalty_rate + Max(0, contract_volume - total_register)'
                '* low_penalty_rate')))
        # TODO DC Sales Tax
    }
)


utilbill_10022_11 = {
    'registers': {
        'total_register': {'quantity': 1271 + 98.8},
    },
    'start': datetime(2012,11,01),
    'end': datetime(2012,01,01),

    # data that the Sempra Energy rate structure requires that others do not
    # require: building size in units
    'num_units': 30,
}


print '*'*80
for rs in (wg_10022, hess_10022):
    for charge_name in sorted(rs._rsis.keys()):
        print '%50s: %8s' % (rs.name + ' - ' + charge_name,
                '%.2f' % Process().compute_charge(rs, charge_name, utilbill_10022_11))

pymongo.Connection('localhost')['temp']['urs'].drop()
