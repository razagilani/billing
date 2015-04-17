from collections import defaultdict
from core import initialize
initialize()

from core.model import Session, UtilBill


s = Session()

descs = defaultdict(lambda: 0)

for ub in s.query(UtilBill).all():
    for r in ub.registers:
        descs[r.description] += 1

for k, v in sorted(descs.items()):
    print "%s %s" % (k, v)

