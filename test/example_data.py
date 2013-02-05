'''Provides example data to be used in tests.'''
import copy
from datetime import date, datetime, timedelta
from bson.objectid import ObjectId
from billing.processing.mongo import MongoReebill, float_to_decimal
from billing.processing.rate_structure import RateStructure
from billing.util import dateutils
from billing.util.dictutils import deep_map, subdict
from billing.util.dateutils import date_to_datetime

# for converting Mongo's JSON directly to Python
ISODate = lambda s: datetime.strptime(s, dateutils.ISO_8601_DATETIME)
true, false = True, False
null = None

# editable utility bill (does not contain sequence, version of reebill)
example_utilbill = {
    # NOTE: "_id" must be inserted at runtime in get_utilbill_dict() because it
    # should be different for each instance

    "account": "10003",
    "service" : "gas",
    "utility" : "washgas",
    "start" : ISODate("2011-11-12T00:00:00Z"),
    "end" : ISODate("2011-12-14T00:00:00Z"),

    "chargegroups" : {
        "All Charges" : [
            {
                "rsi_binding" : "SYSTEM_CHARGE",
                "description" : "System Charge",
                "quantity" : 1,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 11.2,
                "quantity_units" : "",
                "total" : 11.2,
                "uuid" : "c96fc8b0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "DISTRIBUTION_CHARGE",
                "description" : "Distribution charge for all therms",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.2935,
                "quantity_units" : "therms",
                "total" : 164.92,
                "uuid" : "c9709ec0-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "PGC",
                "description" : "Purchased Gas Charge",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.7653,
                "quantity_units" : "therms",
                "total" : 430.02,
                "uuid" : "c9717458-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "PUC",
                "quantity_units" : "kWh",
                "quantity" : 1,
                "description" : "Peak Usage Charge",
                "rate_units" : "dollars",
                "rate" : 23.14,
                "total" : 23.14,
                "uuid" : "c97254b8-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "RIGHT_OF_WAY",
                "description" : "DC Rights-of-Way Fee",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.03059,
                "quantity_units" : "therms",
                "total" : 17.19,
                "uuid" : "c973271c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "SETF",
                "description" : "Sustainable Energy Trust Fund",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.01399,
                "quantity_units" : "therms",
                "total" : 7.87,
                "uuid" : "c973320c-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "EATF",
                "description" : "DC Energy Assistance Trust Fund",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.006,
                "quantity_units" : "therms",
                "total" : 3.37,
                "uuid" : "c973345a-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "SALES_TAX",
                "description" : "Sales tax",
                "quantity" : 701.41,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.06,
                "quantity_units" : "dollars",
                "total" : 42.08,
                "uuid" : "c9733676-2c16-11e1-8c7f-002421e88ffb"
            },
            {
                "rsi_binding" : "DELIVERY_TAX",
                "description" : "Delivery tax",
                "quantity" : 561.9,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.07777,
                "quantity_units" : "therms",
                "total" : 43.7,
                "uuid" : "c973386a-2c16-11e1-8c7f-002421e88ffb"
            }
        ]
    },
    "serviceaddress" : {
        "postalcode" : "20010",
        "city" : "Washington",
        "state" : "DC",
        "addressee" : "Monroe Towers",
        "street" : "3501 13TH ST NW #WH"
    },
    "meters" : [
        {
            "present_read_date" : ISODate("2011-12-14T00:00:00Z"),
            "registers" : [
                {
                    "quantity_units" : "therms",
                    "quantity" : 561.9,
                    "register_binding" : "REG_TOTAL",
                    "identifier" : "M60324",
                    "type" : "total",
                    "description" : "Therms"
                },
            ],
            "prior_read_date" : ISODate("2011-11-12T00:00:00Z"),
            "identifier" : "M60324"
        }
    ],
    "total" : 743.49,
    "rate_structure_binding" : "DC Non Residential Non Heat",
    "billingaddress" : {
        "postalcode" : "20910",
        "city" : "Silver Spring",
        "state" : "MD",
        "addressee" : "Managing Member Monroe Towers",
        "street" : "3501 13TH ST NW LLC"
    }
}

example_reebill = {
	"_id" : {
		"account" : "10003",
		"version" : 0,
		"sequence" : 17
	},
	"ree_charges" : 118.42,
	"ree_value" : 236.84,
	"discount_rate" : 0.5,
    'late_charge_rate': 0.1,
    'late_charges': 12.34,
	"message" : null,
	"issue_date" : null,
	"utilbills" : [
        {
            # NOTE: "id" must be inserted at runtime in get_utilbill_dict() because it
            # should be different for each instance

            "ree_charges" : 118.42,
            "ree_savings" : 118.42,
            "ree_value" : 236.84,

            'shadow_registers': [{
                "quantity_units" : "therms",
                "quantity" : 188.20197727,
                "register_binding" : "REG_TOTAL",
                "identifier" : "M60324",
                "type" : "total",
                "description" : "Therms"
            }],

            "hypothetical_total" : 980.33,
            "hypothetical_chargegroups" : {
                "All Charges" : [
                    {
                        "rsi_binding" : "SYSTEM_CHARGE",
                        "description" : "System Charge",
                        "quantity" : 1,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 11.2,
                        "quantity_units" : "",
                        "total" : 11.2,
                        "uuid" : "c9733cca-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "DISTRIBUTION_CHARGE",
                        "description" : "Distribution charge for all therms",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.2935,
                        "quantity_units" : "therms",
                        "total" : 220.16,
                        "uuid" : "c9733ed2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "PGC",
                        "description" : "Purchased Gas Charge",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.7653,
                        "quantity_units" : "therms",
                        "total" : 574.05,
                        "uuid" : "c97340da-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "PUC",
                        "quantity_units" : "kWh",
                        "quantity" : 1,
                        "description" : "Peak Usage Charge",
                        "rate_units" : "dollars",
                        "rate" : 23.14,
                        "total" : 23.14,
                        "uuid" : "c97342e2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "RIGHT_OF_WAY",
                        "description" : "DC Rights-of-Way Fee",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.03059,
                        "quantity_units" : "therms",
                        "total" : 22.95,
                        "uuid" : "c97344f4-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "SETF",
                        "description" : "Sustainable Energy Trust Fund",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.01399,
                        "quantity_units" : "therms",
                        "total" : 10.5,
                        "uuid" : "c97346f2-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "EATF",
                        "description" : "DC Energy Assistance Trust Fund",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.006,
                        "quantity_units" : "therms",
                        "total" : 4.5,
                        "uuid" : "c9734af8-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "SALES_TAX",
                        "description" : "Sales tax",
                        "quantity" : 924.84,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.06,
                        "quantity_units" : "dollars",
                        "total" : 55.49,
                        "uuid" : "c9734f3a-2c16-11e1-8c7f-002421e88ffb"
                    },
                    {
                        "rsi_binding" : "DELIVERY_TAX",
                        "description" : "Delivery tax",
                        "quantity" : 750.10197727,
                        "rate_units" : "dollars",
                        "processingnote" : "",
                        "rate" : 0.07777,
                        "quantity_units" : "therms",
                        "total" : 58.34,
                        "uuid" : "c9735372-2c16-11e1-8c7f-002421e88ffb"
                    }
                ]
            },
        }
    ],
	"payment_received" : 10,
	"version" : 0,
	"period_end" : ISODate("2011-12-14T00:00:00Z"),
	"actual_total" : 743.49,
	"due_date" : null,
	"service_address" : {
		"sa_city" : "Washington",
		"sa_state" : "DC",
		"sa_addressee" : "Monroe Towers",
		"sa_postal_code" : "20010",
		"sa_street1" : "3501 13TH ST NW #WH"
	},
	"total_adjustment" : 0,
	"ree_savings" : 118.42,
	"statistics" : {
		"renewable_utilization" : 0.26,
		"renewable_produced" : null,
		"total_conventional_consumed" : 95850000,
		"total_co2_offset" : 53443.7978407542,
		"conventional_consumed" : 56190000,
		"total_renewable_produced" : null,
		"total_savings" : 2380.14,
		"consumption_trend" : [
			{ "quantity" : 176.070325956, "month" : "Dec" },
			{ "quantity" : 131.326916818, "month" : "Jan" },
			{ "quantity" : 208.930598627, "month" : "Feb" },
			{ "quantity" : 254.056862159, "month" : "Mar" },
			{ "quantity" : 261.959046815, "month" : "Apr" },
			{ "quantity" : 292.214836348, "month" : "May" },
			{ "quantity" : 300.407399538, "month" : "Jun" },
			{ "quantity" : 389.158304182, "month" : "Jul" },
			{ "quantity" : 331.316663376, "month" : "Aug" },
			{ "quantity" : 191.795145461, "month" : "Sep" },
			{ "quantity" : 240.325501002, "month" : "Oct" },
			{ "quantity" : 211.297853513, "month" : "Nov" }
		],
		"conventional_utilization" : 0.74,
		"total_trees" : 41.110613723657075,
		"co2_offset" : 2533.1986140542,
		"total_renewable_consumed" : 42455175.5556,
		"renewable_consumed" : 18820197.727
	},
	"balance_due" : 1146.21,
	#"account" : "10003", # i think this should not be here
	"prior_balance" : 1027.79,
	"hypothetical_total" : 980.33,
	"balance_forward" : 1027.79,
	"period_begin" : ISODate("2011-11-12T00:00:00Z"),
	"billing_address" : {
		"ba_addressee" : "Managing Member Monroe Towers",
		"ba_state" : "MD",
		"ba_city" : "Silver Spring",
		"ba_street1" : "3501 13TH ST NW LLC",
		"ba_postal_code" : "20910"
	}
}

example_urs = {
	"_id" : {
		"type" : "URS",
		"rate_structure_name" : "DC Non Residential Non Heat",
		"utility_name" : "washgas",
        "effective": datetime(2000, 1, 1),
        "expires": datetime(2020, 12, 31)
	},
	"registers" : [
		{
			"quantity_units" : "therms",
			"description" : "Total therms register",
			"uuid" : "b11e375c-01a9-11e1-af85-002421e88ffb",
			"register_binding" : "REG_TOTAL",
			"quantityunits" : "therms",
			"quantity" : "0"
		}
	],
	"rates" : [
		{
			"rsi_binding" : "SYSTEM_CHARGE",
			"description" : "System Charge",
			"rate_units" : "dollars",
			"uuid" : "b11e2500-01a9-11e1-af85-002421e88ffb",
			"rate" : "26.3",
			"quantity" : 1
		},
		{
			"description" : "Delivery tax",
			"rate" : "0.07777",
			"rsi_binding" : "DELIVERY_TAX",
			"uuid" : "b11e3216-01a9-11e1-af85-002421e88ffb",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"description" : "Sales tax",
			"rate" : "0.06",
			"rsi_binding" : "SALES_TAX",
			"uuid" : "b11e33d8-01a9-11e1-af85-002421e88ffb",
			"quantity" : "SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + PUC.total +  RIGHT_OF_WAY.total + SETF.total + EATF.total + DELIVERY_TAX.total + PGC.total"
		}
	]
}

# the data in this Utility Periodic Rate Structure are made up--as of when i
# made this, we have no nonempty URPSs.
example_uprs = {
	"_id" : {
		"type" : "UPRS",
		"rate_structure_name" : "DC Non Residential Non Heat",
		"utility_name" : "washgas",
        # added with rate structure prediction feature
        'account': '10003',
        'sequence': 17,
        # no longer used
        "effective": datetime(2000, 1, 1),
        "expires": datetime(2020, 12, 31)
	},
	"rates" : [
		{
			"rsi_binding" : "SYSTEM_CHARGE",
			"description" : "System Charge",
			"rate_units" : "dollars",
			"uuid" : "b11e2500-01a9-11e1-af85-002422358023",
			"rate" : "45.6",
			"quantity" : 1
		},
		{
			"description" : "Delivery tax",
			"rate" : "0.1",
			"rsi_binding" : "DELIVERY_TAX",
			"uuid" : "b11e3216-01a9-11e1-af85-560964835ffb",
			"quantity" : "REG_TOTAL.quantity"
		},
	]
}

example_cprs = {
	"_id" : {
		"account" : "10003",
		"sequence" : 17,
		"utility_name" : "washgas",
		"rate_structure_name" : "DC Non Residential Non Heat",
		"version" : 0,
		"type" : "CPRS"
	},
	"rates" : [
		{
			"rsi_binding" : "SYSTEM_CHARGE",
			"uuid" : "af91ba26-01a9-11e1-af85-002421e88ffb",
			"rate_units" : "dollars",
			"rate" : "11.2",
			"total" : 11.2,
			"quantity" : "1"
		},
		{
			"rate" : "0.03059",
			"rsi_binding" : "RIGHT_OF_WAY",
			"uuid" : "af91bfda-01a9-11e1-af85-002421e88ffb",
			"roundrule" : "ROUND_HALF_EVEN",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"rate" : "0.01399",
			"rsi_binding" : "SETF",
			"uuid" : "af91c17e-01a9-11e1-af85-002421e88ffb",
			"roundrule" : "ROUND_UP",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"rate" : "0.006",
			"rsi_binding" : "EATF",
			"uuid" : "af91c318-01a9-11e1-af85-002421e88ffb",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"rsi_binding" : "DELIVERY_TAX",
			"uuid" : "af91c4bc-01a9-11e1-af85-002421e88ffb",
			"rate_units" : "dollars",
			"rate" : "0.07777",
			"quantity_units" : "therms",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"rate" : "0.06",
			"rsi_binding" : "SALES_TAX",
			"uuid" : "af91c674-01a9-11e1-af85-002421e88ffb",
			"quantity" : "SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + PGC.total + RIGHT_OF_WAY.total + PUC.total + SETF.total + EATF.total + DELIVERY_TAX.total"
		},
		{
			"uuid" : "a77bf062-2108-11e1-98b3-002421e88ffb",
			"rate" : "23.14",
			"rsi_binding" : "PUC",
			"description" : "Peak Usage Charge",
			"quantity" : "1"
		},
		{
			"rate" : ".2935",
			"rsi_binding" : "DISTRIBUTION_CHARGE",
			"uuid" : "8ced8464-4dc1-11e1-ab51-002421e88ffb",
			"roundrule" : "ROUND_UP",
			"quantity" : "REG_TOTAL.quantity"
		},
		{
			"rate" : ".7653",
			"rsi_binding" : "PGC",
			"uuid" : "c6b809f8-4dc1-11e1-bba8-002421e88ffb",
			"quantity" : "REG_TOTAL.quantity"
		}
	]
}

def get_reebill(account, sequence, start=date(2011,11,12),
        end=date(2011,12,14), version=0):
    '''Returns an example reebill with the given account and sequence.'''
    reebill_dict = copy.deepcopy(example_reebill)
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

    return MongoReebill(deep_map(float_to_decimal, reebill_dict),
            [copy.deepcopy(deep_map(float_to_decimal, u))])

def get_utilbill_dict(account, start=date(2011,11,12), end=date(2011,12,14),
        utility='washgas', service='gas'):
    '''Returns an example utility bill dictionary.'''
    start, end = date_to_datetime(start), date_to_datetime(end)
    utilbill_dict = copy.deepcopy(example_utilbill)
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

def get_urs_dict():
    '''Returns an example utility global rate structure document.'''
    urs_dict = copy.deepcopy(example_urs)
    return urs_dict

def get_uprs_dict(account, sequence, version=0,
        rate_structure_name='DC Non Residential Non Heat',
        utility_name='washgas'):
    '''Returns an example customer periodic rate structure document.'''
    uprs_dict = copy.deepcopy(example_uprs)
    uprs_dict['_id'].update({
        'account': account,
        'sequence': sequence,
        'version': version,
        'rate_structure_name': rate_structure_name,
        'utility_name': utility_name,
    })
    return uprs_dict

def get_cprs_dict(account, sequence, version=0):
    '''Returns an example utility customer periodic rate structure document
    with the given account and sequence.'''
    cprs_dict = copy.deepcopy(example_cprs)
    cprs_dict['_id']['account'] = account
    cprs_dict['_id']['sequence'] = sequence
    cprs_dict['_id']['version'] = version
    #return RateStructure(cprs_dict)
    return cprs_dict

