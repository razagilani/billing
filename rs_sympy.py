from sympy import Symbol, Piecewise, Float, Basic, oo
from copy import copy
from pprint import PrettyPrinter
pp = PrettyPrinter().pprint

def one():
    q = Symbol('q')

    system_charge = Float(36.25)
    energy_first_block = Piecewise(
        (.3050 * q, q < 300),
        (.3050 * 300, True))
    energy_second_block = Piecewise(
        (0, q < 300),
        (.2124 * (q-300), q < 7000),
        (.2124 * 6700, True)
    )
    energy_remainder_block = Piecewise(
        (0, q < 7000),
        (.1573 * (q - 7000), True)
    )
    md_state_sales_tax = .06 * (system_charge + energy_first_block +
            energy_second_block + energy_remainder_block)
    md_gross_receipts_surcharge = Float(0)
    pg_county_energy_tax = .065 * q
    supply_commodity = .71 * q
    supply_balancing = .014 * q
    md_supply_sales_tax = .06 * (supply_commodity * supply_balancing)

    value = 386.1

    print 'system_charge', system_charge.subs(q, value)
    print 'energy_first_block', energy_first_block.subs(q, value)
    print 'energy_second_block', energy_second_block.subs(q, value)
    print 'energy_remainder_block', energy_remainder_block.subs(q, value)
    print 'md_state_sales_tax', md_state_sales_tax.subs(q, value)
    print 'md_gross_receipts_surcharge', md_gross_receipts_surcharge.subs(q, value)
    print 'pg_county_energy_tax', pg_county_energy_tax.subs(q, value)
    print 'supply_commodity', supply_commodity.subs(q, value)
    print 'supply_balancing', supply_balancing.subs(q, value)
    print 'md_supply_sales_tax', md_supply_sales_tax.subs(q, value)

def two():
    q = Symbol('quantity')

    def block(low, high, rate):
        return Piecewise((0, q < low), (rate * (q - low), q < high), (rate * (high - low), True))

    # constant charges
    md_gross_receipts_surcharge = Float(0)
    system_charge = Float(36.25)

    # quantity-dependent charges
    energy_first_block = block(0, 300, .3050)
    energy_second_block = block(300, 7000, .2124)
    energy_remainder_block = block(7000, oo, .1573)
    supply_commodity = .71 * q
    supply_balancing = .014 * q
    pg_county_energy_tax = .065 * q

    # charge-dependent charges
    md_state_sales_tax = .06 * (system_charge + energy_first_block +
            energy_second_block + energy_remainder_block)
    md_supply_sales_tax = .06 * (supply_commodity * supply_balancing)

    total = md_gross_receipts_surcharge + system_charge + energy_first_block \
            + energy_second_block + energy_remainder_block + supply_commodity \
            + supply_balancing + pg_county_energy_tax + md_state_sales_tax \
            + md_supply_sales_tax

    # SymPy pyglet plotting
    #from sympy import Plot
    #p = Plot(visible=False)
    #p[1] = energy_first_block, [q, 0, 1000]
    #p[2] = energy_second_block, [q, 0, 1000]
    #p[3] = energy_remainder_block, [q, 0, 1000]
    #p.show()

    # SymPy mpmath (matplotlib) plotting
    from sympy import mpmath, cos, sin
    #mpmath.plot([cos, sin], [-4, 4])
    mpmath.plot([
        lambda v: energy_first_block.subs(q,v),
        lambda v: energy_second_block.subs(q,v),
        lambda v: energy_remainder_block.subs(q,v),
        lambda v: (energy_first_block + energy_second_block + energy_remainder_block).subs(q,v),
        #lambda v: total.subs(q,v),
    ], [0, 10000])


def three():
    from StringIO import StringIO
    from sympy import mpmath
    from billing.dictutils import dict_merge

    q = Symbol('quantity')

    def block(low, high, rate):
        return Piecewise((0, q < low), (rate * (q - low), q < high), (rate * (high - low), True))

    io = StringIO('''
md_gross_receipts_surcharge = Float(0)
system_charge = Float(36.25)
energy_first_block = block(0, 300, .3050)
energy_second_block = block(300, 7000, .2124)
energy_remainder_block = block(7000, oo, .1573)
supply_commodity = .71 * q
supply_balancing = .014 * q
pg_county_energy_tax = .065 * q
md_state_sales_tax = .06 * (system_charge + energy_first_block + energy_second_block + energy_remainder_block)
md_supply_sales_tax = .06 * (supply_commodity + supply_balancing)
''')

    charges = { }
    for line in io.readlines():
        if line.strip() == '': continue

        # line should be of the form "name = code"
        name, code = map(str.strip, line.split('='))

        # variables in scope for code evaluation consist of all charge
        # functions named so far + some basic identifiers (SymPy symbols and
        # ones i have defined)
        scope = dict_merge(charges,
                {'q': q, 'Float': Float, 'block': block, 'oo':oo})

        # evaluate 'code' in 'scope' to get a SymPy expression, and store that
        # in 'charges' with 'name' as the key
        charges[name] = eval(code, scope)

    #functions = []
    #for name, expr in charges.items():
        #if name == 'energy_second_block':
            #print '*** "%s": %s' % ( name, expr)
            #func = lambda x: float(expr.subs(q,x))
            #print '&&& %s' % [func(y) for y in range(100,1000,100)]
            ##functions.append(lambda x: expr.subs(q,x))
            #functions.append(func)
    #print functions
    #f = lambda x: block(300, 7000, .2124).subs(q,x)
    ##f = functions[0]
    #values = [f(x) for x in range(100,1000,100)]
    #for value in values:
        #print value
    #mpmath.plot([f])

    #e = charges['energy_second_block']
    #print e, type(e)
    #f = lambda x: float(e.subs(q,x))
    #print f
    #print [f(x) for x in range(100,400, 10)]
    #mpmath.plot([f], [0,500])

    functions = []
    for name, expr in charges.iteritems():
        if name.startswith('energy'):
            f = lambda x: expr.subs(q,x)
            functions.append(f)
            print name, expr
            mpmath.plot(f, [0, 10000])
    #mpmath.plot(functions, [0,10000])

    #mpmath.plot([lambda x: expr.subs(q,x)
        #for (name, expr) in charges.items() if name.startswith('energy')],
            #[0, 10000])


if __name__ == '__main__':
    three()
