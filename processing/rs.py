'''Rate stucture design experiments.'''

class RateStructure(object):
    def __init__(self, charge_rules):
        self.charge_rules = charge_rules

    def get_charge(self, charge_name, quantity):
        price_function = self.charge_rules[charge_name]
        return price_function(quantity)

class BlockRateStructure(RateStructure):
    def __init__(self, blocks):
        rules = {}

        # a block is a dict {min_quantity: ..., rate: ...) such that the customer
        # is charged for min_quantity * rate only if their quantity exceeds minimum
        # quantity and for no more than rate * the next-lowest min_quantity.

        # sort blocks by their min quantity
        blocks = sorted(blocks, key = lambda b: b['min_quantity'])

        for i, block in enumerate(blocks):
            # for each energy block, add a rule computing the charge for energy
            # in that block
            def block_price_function(q):
                if q < block['min_quantity']:
                    return 0
                if i == len(blocks) - 1:
                    return q * block['rate']
                return min(q, blocks[i+1]['min_quantity']) * block['rate']
            rules['block %s' % (i+1)] = block_price_function

        super(BlockRateStructure, self).__init__(rules)

class BlockRateStructure2(RateStructure):
    '''This version knows about its own blocks and can return information about
    them, rather tham just using them to make a set of pricing rules of the
    form used in the plain RateStructure above.'''

    def __init__(self, blocks):
        self.blocks = sorted(blocks, key = lambda b: b['min_quantity'])

    def which_block(self, quantity):
        i = len(self.blocks)-1
        while self.blocks[i]['min_quantity'] > quantity:
            i -= 1
        return i

    def get_marginal_price(self, quantity):
        block = self.blocks[self.which_block(quantity)]
        return block['rate']

# plain rate structure example
#rs = RateStructure({
    #'flat energy rate': lambda q: q * 1.12345,
    #'constant charge': lambda q: 10,
#})
#for q in [0., 10., 20., 30.]:
    #energy_charge = rs.get_charge('flat energy rate', q)
    #const_charge = rs.get_charge('constant charge', q)
    #total = energy_charge + const_charge
    #print "$%s for %s therms + constant charge of $%s = $%s" % (energy_charge, q, const_charge, total)

# block rate structure example
brs = BlockRateStructure([
    {'min_quantity': 0, 'rate': 1.2},
    {'min_quantity': 10, 'rate': 1.1},
    {'min_quantity': 20, 'rate': 1.0},
])
print brs.charge_rules

for q in [0, 5, 10, 15, 20, 25]:
    block_1_charge = brs.get_charge('block 1', q)
    block_2_charge = brs.get_charge('block 2', q)
    block_3_charge = brs.get_charge('block 3', q)
    total = block_1_charge + block_2_charge + block_3_charge
    print "%s: %s in block 1 = %s, %s in block 2 = $%s, %s in block 3 = $%s" % (q, -1, block_2_charge, -1, block_2_charge, -1, block_3_charge)

# block rate structure 2 example
brs2 = BlockRateStructure2([
    {'min_quantity': 0, 'rate': 1.2},
    {'min_quantity': 10, 'rate': 1.1},
    {'min_quantity': 20, 'rate': 1.0},
])
print brs2.blocks
for q in range(30):
    print 'quantity %f: in block %s, marginal rate is %s' % (q, brs2.which_block(q), brs2.get_marginal_price(q))
