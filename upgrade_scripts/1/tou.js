// customers with tou registers:
// early 10001 (1st 4 bills; rely on pdf, not xml)
// 10017
// 10018

use skyline-dev; // TODO change to skyline-stage or skyline or whatever

var daves1 = db.reebills.findOne({'_id.account':'10001', '_id.sequence':1});
var daves2 = db.reebills.findOne({'_id.account':'10001', '_id.sequence':2});
var daves3 = db.reebills.findOne({'_id.account':'10001', '_id.sequence':3});
var daves4 = db.reebills.findOne({'_id.account':'10001', '_id.sequence':4});
// these bills don't have rate structure binding

var treia1 = db.reebills.findOne({'_id.account':'10001', '_id.sequence':1});
// this customer's utility name is "bge", and rate structure binding is "DC
// Residential-R-Winter", but there are actually no rate structures for bge
// (URS, UPRS, or CPRS).
var treia1_ratestrucutre = db.ratestructure.findOne({'_id.type':'URS',
    '_id.rate_structure_name':'DC Residential-R-Winter',
    '_id.utility_name':'bge'});
// actually it's: { "_id" : { "type" : "URS", "rate_structure_name" : "Large General Service - TOU - Schedule GL - POLR Type II (summer)", "utility_name" : "bge" } }
// the following is just a guess about what the register subdocuments will look like
var treia1_peak = {
    "register_binding"  "REG_PEAK",
    "description": "Peak register",
    "uuid": ...
    "quantity_units" : "kWh",
    'active_periods_weekday': [...],
    'active_periods_weekend': [...],
    'active_periods_holiday': [...],
}
var treia1_intermediate = {
    "register_binding" : "REG_INTERMEDIATE",
    "description": "Intermediate register (between peak and off-peak)",
    "uuid": ...
    "quantity_units" : "kWh",
    'active_periods_weekday': [...],
    'active_periods_weekend': [...],
    'active_periods_holiday': [...],
}
var treia1_offpeak = {
    "register_binding": "REG_OFFPEAK",
    "description": "Off-peak register",
    "uuid": ...
    "quantity_units" : "kWh",
    'active_periods_weekday': [...],
    'active_periods_weekend': [...],
    'active_periods_holiday': [...],
}
treia1_ratestructure.registers.push(treia1_peak);
treia1_ratestructure.registers.push(treia1_intermediate);
treia1_ratestructure.registers.push(treia1_offpeak);

// var autumn1 = 
// actually, there are no bills for 10018 yet on tyrell

//> db.ratestructure.findOne({'_id.type':'URS', '_id.utility_name':'bge'})
//{
//    "_id" : {
//        "type" : "URS",
//        "rate_structure_name" : "Large General Service - TOU - Schedule GL - POLR Type II (summer)",
//        "utility_name" : "bge"
//    },
//    "registers" : [
//        {
//            "register_binding" : "REG_TOTAL",
//            "description" : "Total kWh register",
//            "uuid" : "d784a3bc-f511-11e0-8888-002421e88ffb",
//            "quantityunits" : "kWh",
//            "quantity" : "0",
//            "quantity_units" : "kWh"
//        },
//        {
//            "register_binding" : "REG_PEAK",
//            "description" : "Total kWh register",
//            "uuid" : "d784a556-f511-11e0-8888-002421e88ffb",
//            "quantityunits" : "kWh",
//            "quantity" : "0",
//            "quantity_units" : "kWh"
//        },
//        {
//            "register_binding" : "REG_INTERMEDIATE",
//            "description" : "Total kWh register",
//            "uuid" : "d784a6f0-f511-11e0-8888-002421e88ffb",
//            "quantityunits" : "kWh",
//            "quantity" : "0",
//            "quantity_units" : "kWh"
//        },
//        {
//            "register_binding" : "REG_OFFPEAK",
//            "description" : "Total kWh register",
//            "uuid" : "d784a894-f511-11e0-8888-002421e88ffb",
//            "quantityunits" : "kWh",
//            "quantity" : "0",
//            "quantity_units" : "kWh"
//        }
//    ],
//}
//
