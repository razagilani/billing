'''Provides example data to be used in tests.
'''

charge_fields = [
        dict(rate='23.14',
            rsi_binding='PUC',
            description='Peak Usage Charge',
            quantity='1'),
        dict(rate='0.03059',
            rsi_binding='RIGHT_OF_WAY',
            roundrule='ROUND_HALF_EVEN',
            quantity='REG_TOTAL.quantity'),
        dict(rate='0.01399',
            rsi_binding='SETF',
            roundrule='ROUND_UP',
            quantity='REG_TOTAL.quantity'),
        dict(rsi_binding='SYSTEM_CHARGE',
            rate='11.2',
            quantity='1'),
        dict(rsi_binding='DELIVERY_TAX',
            rate='0.07777',
            quantity_units='therms',
            quantity='REG_TOTAL.quantity'),
        dict(rate='.2935',
            rsi_binding='DISTRIBUTION_CHARGE',
            roundrule='ROUND_UP',
            quantity='REG_TOTAL.quantity'),
        dict(rate='.7653',
            rsi_binding='PGC',
            quantity='REG_TOTAL.quantity'),
        dict(rate='0.006',
            rsi_binding='EATF',
            quantity='REG_TOTAL.quantity'),
        dict(rate='0.06',
            rsi_binding='SALES_TAX',
            quantity=('SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + '
                      'PGC.total + RIGHT_OF_WAY.total + PUC.total + '
                      'SETF.total + EATF.total + DELIVERY_TAX.total'))]