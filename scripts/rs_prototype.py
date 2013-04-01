from datetime import date, datetime
from bisect import bisect_left
import sympy
from mongoengine import Document, EmbeddedDocument, ListField, StringField, FloatField, IntField, DictField, EmbeddedDocumentField, ReferenceField
from math import floor, ceil

# TODO
# add units (therms, kWh, dollars). SymPy supports units as symbols so use that.

class Process(object):
    '''Does the actual computing of charges. The 'compute_charge' method should
    go in Process or MongoReebill in a real implementation.'''
    def compute_charge(self, urs, charge_name, utilbill):
        rsi = urs._rsis[charge_name]
        formula_expr = sympy.sympify(rsi.formula)

        # get a value for each input and register that occurs in the formula
        # with the utility bill
        symbol_values = {}
        for symbol in formula_expr.atoms(sympy.Symbol):
            value = getattr(urs, symbol.name)
            # some values are functions of the utility bill; others are constant
            if hasattr(value, '__call__'):
                symbol_values[symbol] = value(utilbill)
            else:
                symbol_values[symbol] = value

        #print '%s = %s' % (charge_name, formula_text)
        #print 'input values %s' % symbol_values

        # substitute values of expressions to evaluate it into a float
        unrounded_charge = formula_expr.subs(symbol_values)

        if rsi.round_rule is None:
            return round(unrounded_charge, 2)
        if rsi.round_rule is 'down':
           return floor(100 * unrounded_charge) / 100.
        if rsi.round_rule is 'up':
           return ceil(100 * unrounded_charge) / 100.
       # TODO add more
        raise ValueError('Unknown rounding rule "%s"' % rsi.round_rule)

class TimeDependentValue(EmbeddedDocument):
    '''RateStructure subdocument representing a value that changes over time.
    We should probably assume every value is one of these, even if we have
    never seen it change or we think it's not supposed to. It has a list of
    [date, value] pairs; the subclss determines which of the values (or some
    combination of them) is chosen for a utility bill with a given period using
    the corresponding date.'''
    meta = {'allow_inheritance': True}

    # list of [date, value] pairs, where the exact meaning of the date is
    # determined by the mapping rule. each of these pairs represents a
    # condition on the utility bill period.
    # (too bad MongoEngine doesn't let you specify constraints on list length
    # or multiple types for a list)
    date_value_pairs = ListField(field=ListField())

class StartBasedTDV(TimeDependentValue):
    '''A time-dependent value that chooses the last value in the list whose
    date is before the start of the utility bill period.'''
    def __call__(self, utilbill):
        # bill counts as being in the value period if its start date is
        # on/after the value period start date. the last condition that
        # matches is used, so entries can be added from beginning to end.
        for date, value in reversed(self.date_value_pairs):
            if utilbill['start'] >= date:
                # the value for each data can be either callable or
                # constant (but it's probably always constant)
                if hasattr(value, '__call__'):
                    return value(utilbill)
                else:
                    return value
        raise ValueError('No match found for %s' % utilbill['start'])

class ProratedTDV(TimeDependentValue):
    '''A time-dependent value that chooses a value made by "prorating" the
    values of multiple periods according to their number of days of overlap
    with the utility bill period.'''
    def __call__(self, utilbill):
        # the value used is not necessarily the stated value of any one
        # value period. instead, return a weighted average of the values
        # for each value period that overlaps with the bill.
        def overlap(a, b, c, d):
            # wlog assume start1 < start2
            start1, end1, start2, end2 = (a, b, c, d) if a < b else (c, d, a,
                    b)
            if start2 < end1:
                if end2 < end1:
                    return (end2 - start2).days
                return (end1 - start2).days
            return 0
        # (TODO optimization: you don't actually need to compute the overlap
        # for some periods since you know it will be 0.)
        date, value = self.date_value_pairs[0]
        overlap_days = (utilbill['end'] - date).days
        total, total_weight = value * overlap_days, overlap_days
        for i, (date, value) in enumerate(self.date_value_pairs[1:]):
            prev_date = self.date_value_pairs[i-1][0]
            overlap_days = overlap(prev_date, date, utilbill['start'],
                    utilbill['end'])
            total += value * overlap_days
            total_weight += overlap_days
        return total / float(total_weight)


class RSI(EmbeddedDocument):
    '''RSI is supposed to be its own class, but all it has is a string (for
    now). Note there is no separation into "quantity" and "rate". Rounding
    rules may be added.'''
    formula = StringField()
    round_rule = StringField(required=False)

class URS(Document):
    '''General rate structure class. All members should be values of symbols
    that occur in RSI formulas.'''
    meta = {'allow_inheritance': True}

    # human-readable description might be useful
    name = StringField()

    # every rate structure has RSIs (charge name -> formula)
    # TODO should they be stored in this class, where all other members are the
    # values of symbols in RSI formulas?
    _rsis = DictField(field=EmbeddedDocumentField(RSI))

    # functions of utility bills that can be used as symbols in RSI formulas in
    # any rate structure:

    def period(self, utilbill):
        return utilbill['start'], utilbill['end']

    def period_length(self, utilbill):
        return (utilbill['end'] - utilbill['start']).days

class SoCalRS(URS):
    '''Specific rate structure class: contains variables and methods (with
    utilbill argument) that provide values of symbols in RS expressions.'''
    # values that are fixed, but are represented as time-dependent just in case
    # they change
    summer_allowance = EmbeddedDocumentField(StartBasedTDV)
    winter_allowance = EmbeddedDocumentField(StartBasedTDV)
    summer_start_month = EmbeddedDocumentField(StartBasedTDV)
    winter_start_month = EmbeddedDocumentField(StartBasedTDV)

    # really time-dependent values (change every month)
    under_baseline_rate = EmbeddedDocumentField(ProratedTDV)
    over_baseline_rate = EmbeddedDocumentField(ProratedTDV)

    # utility-bill-dependent fixed values
    def climate_zone(self, utilbill):
        # get service address, look up the zone number and return it
        return 1

    def num_units(self, utilbill):
        return utilbill['num_units']

    def days_in_summer(self, utilbill):
        # assume bill period is within calendar year (not accurate in real life)
        summer_start = date(utilbill['start'].year,
                self.summer_start_month, 1)
        summer_end = date(utilbill['start'].year,
                self.winter_start_month, 1)
        if utilbill['start'] <= summer_start:
            return max(0, (utilbill['end'] - summer_end).days)
        elif utilbill['end'] < summer_end:
            return max(0, (utilbill['end'] - utilbill['start']).days)
        return 0

    def days_in_winter(self, utilbill):
        return self.period_length(utilbill) - self.days_in_summer(utilbill)

    # register values
    def total_register(self, utilbill):
        return utilbill['registers']['total_register']['quantity']

class TaxRS(URS):
    # other URSs that this one can depend on (charge names in those must be unique)
    # (TODO enforce name uniqueness?)
    other_rss = ListField(field=ReferenceField(URS))
    # TODO is this a good way to do it? should there be a way to apply to all
    # charges of a certain type without explicitly specifying which URSs?
    # what if the tax is charged only on specific charges within a URS?
    # what if taxes depend on each other, e.g. state tax on top of city tax, or
    # tax on top of an energy-based fee that is considered a tax because it
    # comes from the government instead of the utility? (STATE_REGULATORY and
    # PUBLIC_PURPOSE might be the latter.)

    def all_non_tax(self, utilbill):
        '''Sum of all charges in other_rss.'''
        p = Process()
        return sum(sum(p.compute_charge(urs, charge_name, utilbill) for
                charge_name in urs._rsis.keys()) for urs in self.other_rss)

# based on 10031-7-1
socalrs_instance = SoCalRS(
    name='GM-E Residential',

    # inputs that change monthly (with utility bill periods mapped to calendar
    # periods using the "start" rule). these use the complicated "prorate"
    # mapping rule, meaning that the value that actually gets used in a given
    # bill is usually not any of the specific values below.
    under_baseline_rate = ProratedTDV(
        date_value_pairs= [
            [date(2012,10,1), 0.7282],
            [date(2012,11,1), 0.7282],
            [date(2012,12,1), 0.7282],
        ],
    ),
    over_baseline_rate = ProratedTDV(
        date_value_pairs= [
            [date(2012,10,1), 0.9782],
            [date(2012,11,1), 0.9782],
            [date(2012,12,1), 0.9782],
        ],
    ),

    # inputs that have never changed so far, but may change in the future. the
    # initial value extends indefinitely into the future until a new value is
    # added with a later date.
    customer_charge_rate=StartBasedTDV(
        date_value_pairs=[
            [date(2012,1,1), .16438],
        ],
    ),
    state_regulatory_rate=StartBasedTDV(
        date_value_pairs=[
            [date(2012,1,1), .00068],
        ],
    ),
    public_purpose_rate=StartBasedTDV(
        date_value_pairs=[
            [date(2012,1,1), .08231],
        ],
    ),

    # these inputs are constant. should we treat all inputs as possibly
    # time-dependent even if they're not expected to change? if mapping rules
    # never change, we might be able to assume that some actual values never
    # change either.
    summer_allowance = 2,
    winter_allowance = 3,
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

        # TODO (taxes should be in different URS, and I haven't worked out
        # charges that depend on other charges)
        #'LA City Users': RSI(formula='.01 * ...'),
    }
)

la_tax_rs = TaxRS(
    name = 'LA taxes',
    other_rss=[socalrs_instance],
    _rsis={
        'LA City Users': RSI(formula='.1 * all_non_tax')
    }
)

# we should be using a class for utility bills (see branch utilbill-class) but
# we are currently using raw dictionaries (with more data than this in them)
utilbill_doc = {
    # based on 10031-7
    'registers': {
        'total_register': {'quantity': 440},
    },
    'start': date(2012,11,20),
    'end': date(2013,12,20),

    # data that the Sempra Energy rate structure requires that others do not
    # require: building size in units
    'num_units': 30,
}

#for name in ['Gas Service Under Baseline', 'Gas Service Over Baseline', 'Customer Charge']:
for rs in (socalrs_instance, la_tax_rs):
    for charge_name in sorted(rs._rsis.keys()):
        print '%50s: %6s' % (rs.name + '/' + charge_name,
                '%.2f' % Process().compute_charge(rs, charge_name, utilbill_doc))
