'''Provides example data to be used in tests.'''
from copy import deepcopy
from datetime import date, datetime, timedelta
from bson.objectid import ObjectId
from billing.util import dateutils
from billing.util.dictutils import deep_map, subdict
from billing.util.dateutils import date_to_datetime
from billing.processing.rate_structure2 import RateStructure, RateStructureItem, Register
from billing.processing.mongo import MongoReebill

# for converting Mongo's JSON directly to Python
ISODate = lambda s: datetime.strptime(s, dateutils.ISO_8601_DATETIME)
true, false = True, False
null = None

# editable utility bill (does not contain sequence, version of reebill)
example_utilbill = {
    # NOTE: "_id" must be inserted at runtime in get_utilbill_dict() because it
    # should be different for each instance

    u"account": u"10003",
    u"service" : u"gas",
    u"utility" : u"washgas",
    u"start" : ISODate("2011-11-12T00:00:00Z"),
    u"end" : ISODate("2011-12-14T00:00:00Z"),

    u"chargegroups" : {
        u"All Charges" : [
            {
                u"rsi_binding" : u"SYSTEM_CHARGE",
                u"description" : u"System Charge",
                u"quantity" : 1,
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
                u"rate" : 23.14,
                u"total" : 23.14,
                u"uuid" : u"c97254b8-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                u"rsi_binding" : u"RIGHT_OF_WAY",
                u"description" : u"DC Rights-of-Way Fee",
                u"quantity" : 561.9,
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
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
                #u"rate_units" : u"dollars",
                u"processingnote" : u"",
                u"rate" : 0.07777,
                u"quantity_units" : u"therms",
                u"total" : 43.7,
                u"uuid" : u"c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },
    u"service_address" : {
        u"postal_code" : u"20010",
        u"city" : u"Washington",
        u"state" : u"DC",
        u"addressee" : u"Monroe Towers",
        u"street" : u"3501 13TH ST NW #WH"
    },
    u"meters" : [
        {
            u"present_read_date" : ISODate("2011-12-14T00:00:00Z"),
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
            u"prior_read_date" : ISODate("2011-11-12T00:00:00Z"),
            u"identifier" : u"M60324"
        }
    ],
    u"total" : 743.49,
    u"rate_class" : u"DC Non Residential Non Heat",
    u"billing_address" : {
        u"postal_code" : u"20910",
        u"city" : u"Silver Spring",
        u"state" : u"MD",
        u"addressee" : u"Managing Member Monroe Towers",
        u"street" : u"3501 13TH ST NW LLC"
    }
}

example_reebill = {
	u"_id" : {
		u"account" : u"10003",
		u"version" : 0,
		u"sequence" : 17
	},
	u"ree_charges" : 118.42,
	u"ree_value" : 236.84,
	u"discount_rate" : 0.5,
    'late_charge_rate': 0.1,
    'late_charges': 12.34,
	u"message" : null,
	u"issue_date" : null,
	u"utilbills" : [
        {
            # NOTE: u"id" must be inserted at runtime in get_utilbill_dict() because it
            # should be different for each instance

            u"ree_charges" : 118.42,
            u"ree_savings" : 118.42,
            u"ree_value" : 236.84,

            'shadow_registers': [{
                u"quantity_units" : u"therms",
                u"quantity" : 188.20197727,
                u"register_binding" : u"REG_TOTAL",
                u"identifier" : u"M60324",
                u"type" : u"total",
                u"description" : u"Therms"
            }],

            u"hypothetical_total" : 980.33,
            u"hypothetical_chargegroups" : {
                u"All Charges" : [
                    {
                        u"rsi_binding" : u"SYSTEM_CHARGE",
                        u"description" : u"System Charge",
                        u"quantity" : 1,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 11.2,
                        u"quantity_units" : u"",
                        u"total" : 11.2,
                        u"uuid" : u"c9733cca-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"DISTRIBUTION_CHARGE",
                        u"description" : u"Distribution charge for all therms",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.2935,
                        u"quantity_units" : u"therms",
                        u"total" : 220.16,
                        u"uuid" : u"c9733ed2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"PGC",
                        u"description" : u"Purchased Gas Charge",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.7653,
                        u"quantity_units" : u"therms",
                        u"total" : 574.05,
                        u"uuid" : u"c97340da-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"PUC",
                        u"quantity_units" : u"kWh",
                        u"quantity" : 1,
                        u"description" : u"Peak Usage Charge",
                        #u"rate_units" : u"dollars",
                        u"rate" : 23.14,
                        u"total" : 23.14,
                        u"uuid" : u"c97342e2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"RIGHT_OF_WAY",
                        u"description" : u"DC Rights-of-Way Fee",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.03059,
                        u"quantity_units" : u"therms",
                        u"total" : 22.95,
                        u"uuid" : u"c97344f4-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"SETF",
                        u"description" : u"Sustainable Energy Trust Fund",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.01399,
                        u"quantity_units" : u"therms",
                        u"total" : 10.5,
                        u"uuid" : u"c97346f2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"EATF",
                        u"description" : u"DC Energy Assistance Trust Fund",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.006,
                        u"quantity_units" : u"therms",
                        u"total" : 4.5,
                        u"uuid" : u"c9734af8-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"SALES_TAX",
                        u"description" : u"Sales tax",
                        u"quantity" : 924.84,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.06,
                        u"quantity_units" : u"dollars",
                        u"total" : 55.49,
                        u"uuid" : u"c9734f3a-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        u"rsi_binding" : u"DELIVERY_TAX",
                        u"description" : u"Delivery tax",
                        u"quantity" : 750.10197727,
                        #u"rate_units" : u"dollars",
                        u"processingnote" : u"",
                        u"rate" : 0.07777,
                        u"quantity_units" : u"therms",
                        u"total" : 58.34,
                        u"uuid" : u"c9735372-2c16-11e1-8c7f-002421e88ffb"
                    }
                ]
            },
        }
    ],
	u"payment_received" : 10,
	u"version" : 0,
	u"period_end" : ISODate("2011-12-14T00:00:00Z"),
	u"actual_total" : 743.49,
	u"due_date" : null,
	u"service_address" : {
		u"city" : u"Washington",
		u"state" : u"DC",
		u"addressee" : u"Monroe Towers",
		u"postal_code" : u"20010",
		u"street1" : u"3501 13TH ST NW #WH"
	},
	u"total_adjustment" : 0,
	"manual_adjustment" : 0,
	u"ree_savings" : 118.42,
	u"statistics" : {
		u"renewable_utilization" : 0.26,
		u"renewable_produced" : null,
		u"total_conventional_consumed" : 95850000,
		u"total_co2_offset" : 53443.7978407542,
		u"conventional_consumed" : 56190000,
		u"total_renewable_produced" : null,
		u"total_savings" : 2380.14,
		u"consumption_trend" : [
			{ u"quantity" : 176.070325956, u"month" : u"Dec" },
			{ u"quantity" : 131.326916818, u"month" : u"Jan" },
			{ u"quantity" : 208.930598627, u"month" : u"Feb" },
			{ u"quantity" : 254.056862159, u"month" : u"Mar" },
			{ u"quantity" : 261.959046815, u"month" : u"Apr" },
			{ u"quantity" : 292.214836348, u"month" : u"May" },
			{ u"quantity" : 300.407399538, u"month" : u"Jun" },
			{ u"quantity" : 389.158304182, u"month" : u"Jul" },
			{ u"quantity" : 331.316663376, u"month" : u"Aug" },
			{ u"quantity" : 191.795145461, u"month" : u"Sep" },
			{ u"quantity" : 240.325501002, u"month" : u"Oct" },
			{ u"quantity" : 211.297853513, u"month" : u"Nov" }
		],
		u"conventional_utilization" : 0.74,
		u"total_trees" : 41.110613723657075,
		u"co2_offset" : 2533.1986140542,
		u"total_renewable_consumed" : 42455175.5556,
		u"renewable_consumed" : 18820197.727
	},
	u"balance_due" : 1146.21,
	#"account" : u"10003", # i think this should not be here
	u"prior_balance" : 1027.79,
	u"hypothetical_total" : 980.33,
	u"balance_forward" : 1027.79,
	u"period_begin" : ISODate("2011-11-12T00:00:00Z"),
	u"billing_address" : {
		u"addressee" : u"Managing Member Monroe Towers",
		u"state" : u"MD",
		u"city" : u"Silver Spring",
		u"street1" : u"3501 13TH ST NW LLC",
		u"postal_code" : u"20910"
	}
}


example_uprs = RateStructure(
    type='UPRS',
    rates=[
        RateStructureItem(
            rsi_binding='SYSTEM_CHARGE',
            description='System Charge',
            quantity='1',
            quantity_units='',
            rate='45.6',
            #rate_units='dollars',
            round_rule='',
            uuid="b11e2500-01a9-11e1-af85-002422358023",
        ),
        RateStructureItem(
            rsi_binding='DELIVERY_TAX',
            description='Delivery Tax',
            quantity='REG_TOTAL.quantity',
            quantity_units='',
            rate='0.1',
            #rate_units='dollars',
            round_rule='',
            uuid="b11e3216-01a9-11e1-af85-560964835ffb",
        ),
        RateStructureItem(
            rsi_binding='DISTRIBUTION_CHARGE',
            description='Distribution charge for all therms',
            quantity='750.10197727',
            quantity_units='therms',
            rate='0.2935',
            #rate_units='dollars',
            round_rule='',
            uuid="c9733ed2-2c16-11e1-8c7f-002421e88ffb",
        ),
        RateStructureItem(
            rsi_binding='pgc',
            description='purchased gas charge',
            quantity='750.10197727',
            quantity_units='therms',
            rate='0.7653',
            #rate_units='dollars',
            round_rule='',
            uuid="c97340da-2c16-11e1-8c7f-002421e88ffb",
        ),
        RateStructureItem(
            rsi_binding='PUC',
            description='Peak Usage Charge',
            quantity='1',
            quantity_units='therms',
            rate='23.14',
            #rate_units='dollars',
            round_rule='',
            uuid="c97342e2-2c16-11e1-8c7f-002421e88ffb",
        ),
        RateStructureItem(
            rsi_binding='RIGHT_OF_WAY',
            description='DC Rights-of-Way Fee',
            quantity='750.10197727',
            quantity_units='therms',
            rate='0.03059',
            #rate_units='dollars',
            round_rule='',
            uuid="c97344f4-2c16-11e1-8c7f-002421e88ffb",
        ),
        RateStructureItem(
            rsi_binding='SETF',
            description='Sustainable Energy Trust Fund',
            quantity='750.10197727',
            quantity_units='therms',
            rate='0.03059',
            #rate_units='dollars',
            round_rule='',
            uuid="c97346f2-2c16-11e1-8c7f-002421e88ffb",
        ),
        RateStructureItem(
            rsi_binding='EATF',
            description='Energy Assistance Trust Fund',
            quantity='750.10197727',
            quantity_units='therms',
            rate='0.006',
            #rate_units='dollars',
            round_rule='',
            uuid="c9734af8-2c16-11e1-8c7f-002421e88ffb",
        ),
    ],
)

#example_cprs = {
    ## NOTE: u"_id" must be inserted at runtime in get_utilbill_dict() because it
    ## should be different for each instance

	#u"rates" : [
		#{
			#u"rsi_binding" : u"SYSTEM_CHARGE",
			#u"uuid" : u"af91ba26-01a9-11e1-af85-002421e88ffb",
			#u"rate_units" : u"dollars",
			#u"rate" : u"11.2",
			#u"total" : 11.2,
			#u"quantity" : u"1"
		#},
		#{
			#u"rate" : u"0.03059",
			#u"rsi_binding" : u"RIGHT_OF_WAY",
			#u"uuid" : u"af91bfda-01a9-11e1-af85-002421e88ffb",
			#u"roundrule" : u"ROUND_HALF_EVEN",
			#u"quantity" : u"REG_TOTAL.quantity"
		#},
		#{
			#u"rate" : u"0.01399",
			#u"rsi_binding" : u"SETF",
			#u"uuid" : u"af91c17e-01a9-11e1-af85-002421e88ffb",
			#u"roundrule" : u"ROUND_UP",
			#u"quantity" : u"REG_TOTAL.quantity"
		#},
		#{
			#u"rate" : u"0.006",
			#u"rsi_binding" : u"EATF",
			#u"uuid" : u"af91c318-01a9-11e1-af85-002421e88ffb",
			#u"quantity" : u"REG_TOTAL.quantity"
		#},
		#{
			#u"rsi_binding" : u"DELIVERY_TAX",
			#u"uuid" : u"af91c4bc-01a9-11e1-af85-002421e88ffb",
			#u"rate_units" : u"dollars",
			#u"rate" : u"0.07777",
			#u"quantity_units" : u"therms",
			#u"quantity" : u"REG_TOTAL.quantity"
		#},
		#{
			#u"rate" : u"0.06",
			#u"rsi_binding" : u"SALES_TAX",
			#u"uuid" : u"af91c674-01a9-11e1-af85-002421e88ffb",
			#u"quantity" : u"SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + PGC.total + RIGHT_OF_WAY.total + PUC.total + SETF.total + EATF.total + DELIVERY_TAX.total"
		#},
		#{
			#u"uuid" : u"a77bf062-2108-11e1-98b3-002421e88ffb",
			#u"rate" : u"23.14",
			#u"rsi_binding" : u"PUC",
			#u"description" : u"Peak Usage Charge",
			#u"quantity" : u"1"
		#},
		#{
			#u"rate" : u".2935",
			#u"rsi_binding" : u"DISTRIBUTION_CHARGE",
			#u"uuid" : u"8ced8464-4dc1-11e1-ab51-002421e88ffb",
			#u"roundrule" : u"ROUND_UP",
			#u"quantity" : u"REG_TOTAL.quantity"
		#},
		#{
			#u"rate" : u".7653",
			#u"rsi_binding" : u"PGC",
			#u"uuid" : u"c6b809f8-4dc1-11e1-bba8-002421e88ffb",
			#u"quantity" : u"REG_TOTAL.quantity"
		#}
	#]
#}

example_cprs = RateStructure(type='CPRS',
    rates=[
		RateStructureItem(
            rsi_binding='SYSTEM_CHARGE',
			uuid='af91ba26-01a9-11e1-af85-002421e88ffb',
			#rate_units='dollars',
			rate='11.2',
			quantity='1'
        ),
        RateStructureItem(
			rate='0.03059',
			rsi_binding='RIGHT_OF_WAY',
			uuid='af91bfda-01a9-11e1-af85-002421e88ffb',
			roundrule='ROUND_HALF_EVEN',
			quantity='REG_TOTAL.quantity'
		),
        RateStructureItem(
			rate='0.01399',
			rsi_binding='SETF',
			uuid='af91c17e-01a9-11e1-af85-002421e88ffb',
			roundrule='ROUND_UP',
			quantity='REG_TOTAL.quantity'
		),
        RateStructureItem(
			rate='0.006',
			rsi_binding='EATF',
			uuid='af91c318-01a9-11e1-af85-002421e88ffb',
			quantity='REG_TOTAL.quantity'
		),
        RateStructureItem(
			rsi_binding='DELIVERY_TAX',
			uuid='af91c4bc-01a9-11e1-af85-002421e88ffb',
			#rate_units='dollars',
			rate='0.07777',
			quantity_units='therms',
			quantity='REG_TOTAL.quantity'
		),
        RateStructureItem(
			rate='0.06',
			rsi_binding='SALES_TAX',
			uuid='af91c674-01a9-11e1-af85-002421e88ffb',
			quantity=('SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + '
                    'PGC.total + RIGHT_OF_WAY.total + PUC.total + '
                    'SETF.total + EATF.total + DELIVERY_TAX.total')
        ),
        RateStructureItem(
			uuid='a77bf062-2108-11e1-98b3-002421e88ffb',
			rate='23.14',
			rsi_binding='PUC',
			description='Peak Usage Charge',
			quantity='1'
		),
        RateStructureItem(
			rate='.2935',
			rsi_binding='DISTRIBUTION_CHARGE',
			uuid='8ced8464-4dc1-11e1-ab51-002421e88ffb',
			roundrule='ROUND_UP',
			quantity='REG_TOTAL.quantity'
		),
        RateStructureItem(
			rate='.7653',
			rsi_binding='PGC',
			uuid='c6b809f8-4dc1-11e1-bba8-002421e88ffb',
			quantity='REG_TOTAL.quantity'
        ),
    ],
)

def get_reebill(account, sequence, start=date(2011,11,12),
        end=date(2011,12,14), version=0):
    '''Returns an example reebill with the given account, sequence, and dates.
    It comes with one utility bill having the same dates.'''
    reebill_dict = deepcopy(example_reebill)
    reebill_dict['_id'].update({
        'account': account,
        'sequence': sequence,
        'version': version,
    })
    reebill_dict['period_begin'] = start
    reebill_dict['period_end'] = end

    id = ObjectId()
    reebill_dict['utilbills'][0]['id'] = id

    u = get_utilbill_dict(account, start=start, end=end)

    # force utilbill to match the utilbill document
    u.update({
        '_id': id,
        'account': account,
        'start': start,
        'end': end
    })

    return MongoReebill(reebill_dict, [deepcopy(u)])

def get_utilbill_dict(account, start=date(2011,11,12), end=date(2011,12,14),
        utility='washgas', service='gas'):
    '''Returns an example utility bill dictionary.'''
    start, end = date_to_datetime(start), date_to_datetime(end)
    utilbill_dict = deepcopy(example_utilbill)
    utilbill_dict.update({
        '_id': ObjectId(),
        'account': account,
        'start': start,
        'end': end,
        'service': service,
        'utility': utility,
    })
    for meter in utilbill_dict['meters']:
        meter['prior_read_date'] = start
        meter['present_read_date'] = end
    return utilbill_dict

def get_uprs():
    result = deepcopy(example_uprs)
    result.id = ObjectId()
    return result

def get_cprs():
    result = deepcopy(example_cprs)
    result.id = ObjectId()
    return result
