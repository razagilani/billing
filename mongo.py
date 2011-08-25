#!/usr/bin/python
import sys
import datetime
from decimal import Decimal
import pymongo
import billing.bill as bill
from billing.mutable_named_tuple import MutableNamedTuple

# this dictionary maps XML element names to MongoDB document keys, for use in
# rename_keys. element names that map to None will be removed instead of
# renamed.
# TODO maybe break into separate dictionaries used for each call to
# rename_keys()
name_changes = {
    # rebill section
    'serviceaddress': 'service_address',
    'billingaddress': 'billing_address',
    'priorbalance': 'prior_balance',
    'paymentrecieved': 'payment_recieved',
    'totaladjustment': 'total_adjustment',
    'balanceforward': 'balance_forward',
    #'hypotheticalecharges': 'hypothetical_e_charges',
    'hypothetical_total': None, # identical to hypothetical_total
    #'actualecharges': 'actual_e_charges',
    'actualecharges': None, # identical to actual_total
    'revalue': 'ree_value',
    'recharges': 'ree_charges',
    'resavings': None,
    'totaldue': 'total_due',
    'duedate': 'due_date',
    'issued': 'issued',
    # utilbill section
    'periodstart': 'periodend',
    'periodend': 'periodstart',
    'rsbinding': 'rate_structure_binding', # also in measuredusage section
    'rateunits': 'rate_units',
    'quantityunits': 'rate_units',
    # measuredusage section
    'presentreaddate': 'present_read_date',
    'priorreaddate': 'prior_read_date',
    'inclusions':None,
    'exclusions':None,
    # statistics section
    'co2offset': 'co2_offset',
    'consumptiontrend': 'consumption_trend',
    'conventional_consumed': 'conventional_consumed',
    'conventionalutilization': 'conventional_utilization',
    'renewableconsumed': 'renewable_consumed',
    'renewableutilization': 'renewable_utilization',
    'totalco2offset': 'total_co2_offset',
    'totalrenewableconsumed': 'total_renewable_consumed',
    'totalsavings': 'total_savings',
    'totaltrees': 'total_trees'
}

def bson_convert(x):
    '''Returns x converted into a type suitable for Mongo.'''
    if type(x) in [str, float, int, bool]:
        return x
    if type(x) is Decimal:
        return float(x)
    if type(x) in [datetime.date, datetime.time]:
        return str(x)
    if type(x) is dict or type(x) is MutableNamedTuple:
        return dict([(item[0], bson_convert(item[1])) for item in x.iteritems()
                if item[1] is not None])
    if type(x) is list:
        return map(bson_convert, x)
    raise ValueError("type(%s) is %s: can't convert that into bson" \
            % (x, type(x)))

def rename_keys(x):
    '''If x is a dictionary or list, recursively replaces keys in x according
    to 'name_changes' above.'''
    if type(x) is dict:
        return dict([(name_changes.get(key,key), rename_keys(value)) \
                for (key,value) in x.iteritems() \
                if not (key in name_changes and name_changes[key] is None)])
    if type(x) is list:
        #return map(rename_keys, x)
        return [rename_keys(element) for element in x]
    return x

#def dict_merge(overwrite=False, *dicts):
def dict_merge(*dicts, **kwargs):
    '''Returns a dictionary consisting of the key-value pairs in all the
    dictionaries passed as arguments. These dictionaries must not share any
    keys.'''
    overwrite = kwargs.get('overwrite', False)
    if not overwrite:
        # throw exception if they have the same keys
        for d in dicts:
            for key in d.keys():
                for other in [other for other in dicts if other is not d]:
                    if key in other.keys():
                        raise ValueError('dictionaries share key "%s"' % key)
    result = {}
    for d in dicts:
        result.update(d)
    return result

def mongo_convert(url):
	'''Returns a dictionary that is the Mongo document representation of the XML reebill at 'url'.'''
	b = bill.Bill(url)

	# top-level reebill information:
	reebill = dict_merge({
			'account': b.account,
			'sequence': b.id,
			# "car" in XML flattened in Mongo (and only 1 billing address allowed)
			'service_address': b.service_address,
			'billing_address': b.billing_address
		},
		rename_keys(bson_convert(b.rebill_summary))
	)

	# TODO
	'''
	replacement for utilbill.rate_structure_binding:
		utility_name: e.g. "washgas",
		rate_schedule: "DC_NONRESIDENTIAL_NONHEAT",
	'''

	'''
	A reebill has a list containing 1 or more utilbills, each of which is
	structured as follows:
	   {
		----- utilbill section -----
		service: "",  <--moved into the utilbill itself
		actual_e_charges: #,
		hypothetical_e_charges: #,
		ree_charges: #,
		ree_value: #,
		----- details section -----
		actual_chargegroups: [
		  chargegroup_type: [
				   {    
					   description: ""
					   quantity: #
					   quantity_units: ""
					   rate: #
					   rate_schedule_binding: ""
					   rate_units: ""
					   total: #
				   },
			   ]
		   ...
		  ],
		  ...
		]
		actual_total: #
		hypothetical_chargegroups: (just like actual_chargegroups)
		hypothetical_total: #
		----- measuredusages section -----
		meters: {
		  {service_name:
			  [identifier: "",
			   present_read_date: date,
			   prior_read_date: date,
			   registers: [
				  {description: ""
				   identifier: ""
				   presentreading: #
				   rate_schedule_binding: ""
				   shadow: boolean
				   total: #
				   type: ""
				   units: ""
				   }
				   ...
			   ]
			   ...
			 }
		  }
		----- statistics section -----
		(exactly the same as XML)
	   }
	'''

	# utilbill info from the actual "utilbill" section
	# (service names moved from keys of the utilbill_summary_charges dict into the
	# utilbills themselves)
	reebill['utilbills'] = [dict_merge({'service':service}, 
			rename_keys(bson_convert(b.utilbill_summary_charges[service])))
			for service in b.utilbill_summary_charges.keys()]

	# utilbill info from "details", "measuredusage", and "statistics" sections of
	# XML ("billableusage" section is completely ignored)
	actual_details = b.actual_details
	hypothetical_details = b.hypothetical_details
	measured_usages = b.measured_usage
	for utilbill in reebill['utilbills']:
		# get hypothetical details and actual details from bill.py
		this_bill_actual_details = actual_details[utilbill['service']]
		this_bill_hypothetical_details = hypothetical_details[utilbill['service']]

		# fill in utilbill
		utilbill.update({
			'rate_schedule_name': this_bill_actual_details.rateschedule.name,
			
			# fail if this bill doesn't have an rsbinding
			'rate_schedule_binding': this_bill_actual_details. \
					rateschedule.rsbinding,
			# so-called rate structure/schedule binding ("rsbinding") in utilbill
			# is actually the name of the utility
			'utility_name': this_bill_actual_details.rateschedule.rsbinding,
			# TODO add rate schedule (not all xml files have this)
			# 'rate_schedule': bson_convert(b.rateschedule),

			# chargegroups are divided between actual and hypothetical; these are
			# stored in 2 dictionaries mapping the name of each chargegroup to a
			# list of its charges. totals (in the format {total: #}) are removed
			# from each list of charges and placed at the root of the utilbill.
			'actual_chargegroups': {
				chargegroup.type: [rename_keys(bson_convert(charge))
				for charge in chargegroup.charges if charge.keys() != ['total']]
				for chargegroup in this_bill_actual_details.chargegroups
			},
			'actual_total': bson_convert(this_bill_actual_details.total),
			'hypothetical_chargegroups': {
				chargegroup.type: [rename_keys(bson_convert(charge))
				for charge in chargegroup.charges if charge.keys() != ['total']]
				for chargegroup in this_bill_hypothetical_details.chargegroups
			},
			'hypothetical_total': bson_convert(this_bill_hypothetical_details.total)
		})

		# measured usages: each utility has one or more meters, each of which has
		# one or more registers (which are like sub-meters)
		meters = measured_usages[utilbill['service']]
		# TODO replace register.inclusions/exclusions with a "descriptor" (a
		# name) that matches the value of 'descriptor' for a register in the 'registers' section of the monthly rate structure yaml file. 
		utilbill.update({'meters': rename_keys(bson_convert(meters))})

	# statistics: exactly the same as in XML
	reebill.update(rename_keys(bson_convert(b.statistics)))

	return reebill

