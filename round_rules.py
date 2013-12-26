#!/usr/bin/python

from decimal import *
import string

for prec in [5, 6, 7, 8]:

    getcontext().prec = prec
    print "Decimal math precision: " + str(prec)

    charges = [Decimal(Decimal('210.9')*Decimal('.2939')), Decimal(Decimal('257')*Decimal('.2939')), Decimal(Decimal('287.7')*Decimal('.2939')), Decimal(Decimal('361.5')*Decimal('.2939'))]
    totals = [Decimal('61.99'), Decimal('75.53'), Decimal('84.55'), Decimal('106.24')]

    print "Calculated Charge: " + str(charges)
    print " Published Totals: " + str(totals)

    for rule in [ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, ROUND_05UP]:

        computed = [charge.quantize(Decimal('.00'), rule) for charge in charges]
        print string.rjust(rule,17) + ": " + str(computed) + (" Matches! " if (computed == totals) else " Doesn't match.")
    print
