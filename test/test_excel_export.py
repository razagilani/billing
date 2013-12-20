#!/usr/bin/env python2
from billing.processing.excel_export import Exporter
from datetime import date

mock_chargegroup1=[{
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 1,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 11.2,
                u"quantity_units" : u"",
                u"total" : 11.2,
                u"uuid" : u"c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DISTRIBUTION_CHARGE",
                u"description" : u"Distribution charge for all therms",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.2935,
                u"quantity_units" : u"therms",
                u"total" : 164.92,
                u"uuid" : u"c9709ec0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"PGC",
                u"description" : u"Purchased Gas Charge",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.7653,
                u"quantity_units" : u"therms",
                u"total" : 430.02,
                u"uuid" : u"c9717458-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"PUC",
                u"quantity_units" : u"kWh",
                u"quantity" : 1,
                u"description" : u"Peak Usage Charge",
                u"rate_units" : u"dollars",
                u"rate" : 23.14,
                u"total" : 23.14,
                u"uuid" : u"c97254b8-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"RIGHT_OF_WAY",
                u"description" : u"DC Rights-of-Way Fee",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.03059,
                u"quantity_units" : u"therms",
                u"total" : 17.19,
                u"uuid" : u"c973271c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SETF",
                u"description" : u"Sustainable Energy Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.01399,
                u"quantity_units" : u"therms",
                u"total" : 7.87,
                u"uuid" : u"c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"EATF",
                u"description" : u"DC Energy Assistance Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.006,
                u"quantity_units" : u"therms",
                u"total" : 3.37,
                u"uuid" : u"c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SALES_TAX",
                u"description" : u"Sales tax",
                u"quantity" : 701.41,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.06,
                u"quantity_units" : u"dollars",
                u"total" : 42.08,
                u"uuid" : u"c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DELIVERY_TAX",
                u"description" : u"Delivery tax",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 43.7,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },{
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 3,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 11.2,
                u"quantity_units" : u"",
                u"total" : 33.6,
                u"uuid" : u"c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DISTRIBUTION_CHARGE",
                u"description" : u"Distribution charge for all therms",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 1,
                u"quantity_units" : u"therms",
                u"total" : 561.9,
                u"uuid" : u"c9709ec0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"PGC",
                u"description" : u"Purchased Gas Charge",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 2,
                u"quantity_units" : u"therms",
                u"total" : 2121.0,
                u"uuid" : u"c9717458-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"PUC",
                u"quantity_units" : u"kWh",
                u"quantity" : 1,
                u"description" : u"Peak Usage Charge",
                u"rate_units" : u"dollars",
                u"rate" : 23.14,
                u"total" : 122.1,
                u"uuid" : u"c97254b8-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"RIGHT_OF_WAY",
                u"description" : u"DC Rights-of-Way Fee",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.03059,
                u"quantity_units" : u"therms",
                u"total" : 12.1,
                u"uuid" : u"c973271c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SETF",
                u"description" : u"Sustainable Energy Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.01399,
                u"quantity_units" : u"therms",
                u"total" : 2.2,
                u"uuid" : u"c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"EATF",
                u"description" : u"DC Energy Assistance Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.006,
                u"quantity_units" : u"therms",
                u"total" : 1.12,
                u"uuid" : u"c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SALES_TAX",
                u"description" : u"Sales tax",
                u"quantity" : 701.41,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.06,
                u"quantity_units" : u"dollars",
                u"total" : 14.43,
                u"uuid" : u"c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DELIVERY_TAX",
                u"description" : u"Delivery tax",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 43.4,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    }]
mock_chargegroup2=[{
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 1,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 11.2,
                u"quantity_units" : u"",
                u"total" : 15.6,
                u"uuid" : u"c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SETF",
                u"description" : u"Sustainable Energy Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.01399,
                u"quantity_units" : u"therms",
                u"total" : 89.2,
                u"uuid" : u"c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"EATF",
                u"description" : u"DC Energy Assistance Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.006,
                u"quantity_units" : u"therms",
                u"total" : 1.1,
                u"uuid" : u"c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SALES_TAX",
                u"description" : u"Sales tax",
                u"quantity" : 701.41,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.06,
                u"quantity_units" : u"dollars",
                u"total" : 79.0,
                u"uuid" : u"c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DELIVERY_TAX",
                u"description" : u"Delivery tax",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 89.0,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },{
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 1,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 11.2,
                u"quantity_units" : u"",
                u"total" : 16.7,
                u"uuid" : u"c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SETF",
                u"description" : u"Sustainable Energy Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.01399,
                u"quantity_units" : u"therms",
                u"total" : 90.5,
                u"uuid" : u"c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"EATF",
                u"description" : u"DC Energy Assistance Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.006,
                u"quantity_units" : u"therms",
                u"total" : 1.1,
                u"uuid" : u"c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SALES_TAX",
                u"description" : u"Sales tax",
                u"quantity" : 701.41,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.06,
                u"quantity_units" : u"dollars",
                u"total" : 68.9,
                u"uuid" : u"c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DELIVERY_TAX",
                u"description" : u"Delivery tax",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 81.0,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },{
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 1,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 11.2,
                u"quantity_units" : u"",
                u"total" : 14.5,
                u"uuid" : u"c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SETF",
                u"description" : u"Sustainable Energy Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.01399,
                u"quantity_units" : u"therms",
                u"total" : 85.62,
                u"uuid" : u"c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"EATF",
                u"description" : u"DC Energy Assistance Trust Fund",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.006,
                u"quantity_units" : u"therms",
                u"total" : 1.3,
                u"uuid" : u"c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"SALES_TAX",
                u"description" : u"Sales tax",
                u"quantity" : 701.41,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.06,
                u"quantity_units" : u"dollars",
                u"total" : 56.43,
                u"uuid" : u"c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"DELIVERY_TAX",
                u"description" : u"Delivery tax",
                u"quantity" : 561.9,
                u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 32.90,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },]


mock_utilbills=[{
    u"service" : u"gas",
    u"start" : date(2011,8,12),
    u"end" : date(2011,9,14),
    u"meters" : [
        {
            u"registers" : [
                {
                    u"quantity_units" : u"therms",
                    u"quantity" : 561.9,
                    u"register_binding" : u"REG_TOTAL",
                    u"identifier" : u"M60324",
                    u"type" : u"total",
                    u"description" : u"Therms"
                },
            ],
            u"identifier" : u"M60324"
        }
    ],
    u"chargegroups" : mock_chargegroup1[0],
    u"rate_structure_binding" : u"DC Non Residential Non Heat",
},{
    u"service" : u"gas",
    u"start" : date(2011,10,12),
    u"end" : date(2011,11,14),
    u"meters" : [
        {
            u"registers" : [
                {
                    u"quantity_units" : u"therms",
                    u"quantity" : 2132.2,
                    u"register_binding" : u"REG_TOTAL",
                    u"identifier" : u"M60324",
                    u"type" : u"total",
                    u"description" : u"Therms"
                },
            ],
            u"identifier" : u"M60324"
        }
    ],
    u"chargegroups" : mock_chargegroup1[1],
    u"rate_structure_binding" : u"DC Non Residential Non Heat",
},{
    u"service" : u"electric",
    u"start" : date(2011,12,12),
    u"end" : date(2012,1,14),
    u"meters" : [
        {
            u"registers" : [
                {
                    u"quantity_units" : u"kwh",
                    u"quantity" : 321,
                    u"register_binding" : u"REG_TOTAL",
                    u"identifier" : u"M60324",
                    u"type" : u"total",
                    u"description" : u"Therms"
                },
            ],
            u"identifier" : u"M60324"
        }
    ],
    u"chargegroups" : mock_chargegroup2[0],
    u"rate_structure_binding" : u"DC Residential Electric",
},{
    u"service" : u"electric",
    u"start" : date(2012,2,12),
    u"end" : date(2012,3,14),
    u"meters" : [
        {
            u"registers" : [
                {
                    u"quantity_units" : u"kwh",
                    u"quantity" : 562.1,
                    u"register_binding" : u"REG_TOTAL",
                    u"identifier" : u"M60324",
                    u"type" : u"total",
                    u"description" : u"Therms"
                },
            ],
            u"identifier" : u"M60324"
        }
    ],
    u"chargegroups" : mock_chargegroup2[1],
    u"rate_structure_binding" : u"DC Residential Electric",
},{
    u"service" : u"electric",
    u"start" : date(2012,4,12),
    u"end" : date(2012,5,14),
    u"meters" : [
        {
            u"registers" : [
                {
                    u"quantity_units" : u"kwh",
                    u"quantity" : 7878.9,
                    u"register_binding" : u"REG_TOTAL",
                    u"identifier" : u"M60324",
                    u"type" : u"total",
                    u"description" : u"Therms"
                },
            ],
            u"identifier" : u"M60324"
        }
    ],
    u"chargegroups" : mock_chargegroup2[2],
    u"rate_structure_binding" : u"DC Residential Electric",
}]

class MockStateDB():
    def __init__(self):
        pass
    def listAccounts(self, session):
        return ['20001','20002']
class MockDAO():
    def __init__(self):
        pass
    def load_utilbills(self,account):
        if account=='20001':
            return [mock_utilbills[0],mock_utilbills[1]]
        else:
            return [mock_utilbills[2],mock_utilbills[3],mock_utilbills[4]]

def main():
    exporter = Exporter(MockStateDB(),MockDAO())
    with open('xbill_energy.xls', 'wb') as output_file:
        exporter.export_energy_usage(None, output_file)

if __name__ == '__main__':
    main()
