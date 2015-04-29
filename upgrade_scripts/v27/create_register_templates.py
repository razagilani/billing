from core.model import RateClass, UtilBill
from core.model.model import RegisterTemplate

LIMIT = 10

def create_register_templates(s, log):
    for rate_class in s.query(RateClass).all():
        # collect register_binding -> (unit, active_periods) for the 'LIMIT'
        # most recent bills in this rate class (last one wins if values differ)
        data = {}
        q = s.query(UtilBill).filter(UtilBill.rate_class == rate_class,
                                     UtilBill.processed == True).order_by(
            UtilBill.period_end).limit(LIMIT)

        for bill in q.all():
            for r in bill.registers:
                data[r.register_binding] = (r.unit, r.active_periods)

        # create RegisterTemplates for all register_bindings found above
        # (skip REG_TOTAL because it's already there)
        for register_binding, (unit, active_periods) in data.iteritems():
            if register_binding == 'REG_TOTAL':
                continue
            rate_class.register_templates.append(
                RegisterTemplate(register_binding=register_binding, unit=unit,
                                 active_periods=active_periods))

        log.info('%s: %s' % (rate_class.name, ', '.join(
                rt.register_binding for rt in rate_class.register_templates)))
    s.commit()
