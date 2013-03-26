from datetime import date, datetime
from bisect import bisect_left
import sympy
from mongoengine import Document, EmbeddedDocument, ListField, StringField, FloatField, IntField, DictField, EmbeddedDocumentField

class Process(object):
    '''Does the actual computing of charges. The 'compute_charge' method should
    go in Process or MongoReebill in a real implementation.'''
    def compute_charge(self, urs, charge_name, utilbill):
        formula_text = urs._rsis[charge_name].formula
        formula_expr = sympy.sympify(formula_text)

        # get a value for each input and register that occurs in the formula
        # with the utility bill
        symbol_values = {}
        for symbol in formula_expr.atoms(sympy.Symbol):
            value = getattr(urs, symbol.name)
            # every value is a function of the utility bill, and every one is
            # assumed to (at least potentially) change over time
            symbol_values[symbol] = value(utilbill)

        print '%s = %s' % (charge_name, formula_text)
        print 'input values %s' % symbol_values

        # substitute values of expressions to evaluate it into a float
        return formula_expr.subs(symbol_values)

class TimeDependentValue(EmbeddedDocument):
    '''RateStructure subdocument representing a value that changes over time.
    We should probably assume every value is one of these, even if we have
    never seen it change or we think it's not supposed to. It has a list of
    [date, value] pairs, plus a "mapping rule" that determines exactly how one
    of the values is chosen for a utility bill with a given period using the
    corresponding date.'''
    # TODO: instead of using a 'mapping_rule' string, maybe create different
    # subclasses of TimeDependentValue for different mapping rules

    # rich says the mapping rule itself never changes--if it does, it's a new
    # rate structure entirely
    mapping_rule = StringField()

    # list of [date, value] pairs, where the exact meaning of the date is
    # determined by the mapping rule. each of these pairs represents a
    # condition on the utility bill period.
    # (too bad MongoEngine doesn't let you specify constraints on list length
    # or multiple types for a list)
    date_value_pairs = ListField(field=ListField())

    def __call__(self, utilbill):
        '''A TimeDependentValue is also a function of a utility bill, like
        other inputs, but it should use only the utility bill's period to
        choose a value.'''

        if self.mapping_rule == 'start':
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

        elif self.mapping_rule == 'prorate':
            # the value used is not necessarily the stated value of any one
            # value period. instead, return a weighted average of the values
            # for each value period that overlaps with the bill.
            def overlap(a, b, c, d):
                # wlog assume start1 < start2
                start1, end1, start2, end2 = (a, b, c, d) if a < b \
                        else (c, d, a, b)
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

        else:
            raise NotImplementedError

class RSI(EmbeddedDocument):
    '''RSI is supposed to be its own class, but all it has is a string (for
    now). Note there is no separation into "quantity" and "rate". Rounding
    rules may be added.'''
    formula = StringField()

class URS(Document):
    '''General rate structure class. All members should be values of symbols
    that occur in RSI formulas.'''
    meta = {'allow_inheritance': True}

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
    summer_allowance = EmbeddedDocumentField(TimeDependentValue)
    winter_allowance = EmbeddedDocumentField(TimeDependentValue)
    summer_start_month = EmbeddedDocumentField(TimeDependentValue)
    winter_start_month = EmbeddedDocumentField(TimeDependentValue)

    # really time-dependent values (change every month)
    under_baseline_rate = EmbeddedDocumentField(TimeDependentValue)
    over_baseline_rate = EmbeddedDocumentField(TimeDependentValue)

    # utility-bill-dependent fixed values
    def climate_zone(self, utilbill):
        # get service address, look up the zone number and return it
        return 1

    def num_units(self, utilbill):
        return utilbill['num_units']

    def days_in_summer(self, utilbill):
        # assume bill period is within calendar year (not accurate in real life)
        summer_start = date(utilbill['start'].year,
                self.summer_start_month(utilbill), 1)
        summer_end = date(utilbill['start'].year,
                self.winter_start_month(utilbill), 1)
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


socalrs_instance = SoCalRS(
    # inputs that change monthly (with utility bill periods mapped to calendar
    # periods using the "start" rule). these use the complicated "prorate"
    # mapping rule, meaning that the value that actually gets used in a given
    # bill is usually not any of the specific values below.
    under_baseline_rate = TimeDependentValue(
        mapping_rule='prorate',
        date_value_pairs= [
            [date(2013,1,1), 1.1],
            [date(2013,2,1), 1.2],
            [date(2013,3,1), 1.3],
        ],
    ),
    over_baseline_rate = TimeDependentValue(
        mapping_rule='prorate',
        date_value_pairs= [
            [date(2013,1,1), 2.1],
            [date(2013,2,1), 2.2],
            [date(2013,3,1), 2.3],
        ],
    ),

    # all inputs are time-dependent, but we have never seen these change so
    # far. they use the "start" mapping rule by default, and we expect we will
    # never have to add more entries in 'date_value_pairs'
    summer_allowance = TimeDependentValue(
        mapping_rule='start',
        date_value_pairs=[
            [date(2013,1,1), 2],
        ],
    ),
    winter_allowance = TimeDependentValue(
        mapping_rule='start',
        date_value_pairs=[
            [date(2013,1,1), 3],
        ],
    ),
    summer_start_month = TimeDependentValue(
        mapping_rule='start',
        date_value_pairs=[
            [date(2013,1,1), 4],
        ],
    ),
    winter_start_month = TimeDependentValue(
        mapping_rule='start',
        date_value_pairs=[
            [date(2013,1,1), 10],
        ],
    ),

    # RSI formulas, named with underscore to distinguish from symbol names
    # (TODO maybe these move somewhere else? or find some other way of
    # distinguishing them from the inputs?)
    _rsis = {
        'Gas Service Over Baseline':
            RSI(formula=('over_baseline_rate * Max(0, total_register - num_units *'
            '(winter_allowance * days_in_winter + summer_allowance * '
            'days_in_summer))')),
        'Gas Service Under Baseline':
            RSI(formula=('under_baseline_rate * Min(total_register, num_units * '
            '(winter_allowance * days_in_winter + summer_allowance * '
            'days_in_summer))')),
    }
)

# we should be using a class for utility bills (see branch utilbill-class) but
# we are currently using raw dictionaries (with more data than this in them)
utilbill_doc = {
    'registers': {
        'total_register': {'quantity': 100},
    },
    'start': date(2013,1,15),
    'end': date(2013,2,15),

    # data that the Sempra Energy rate structure requires that others do not
    # require: building size in units
    'num_units': 50,
}

for name in ['Gas Service Under Baseline', 'Gas Service Over Baseline']:
    print '%s: $%.2f' % (name, Process().compute_charge(socalrs_instance, name, utilbill_doc))
