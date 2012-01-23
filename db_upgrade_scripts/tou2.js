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
var treia1_ratestructure = db.ratestructure.findOne({'_id.type':'URS',
    '_id.rate_structure_name':'DC Residential-R-Winter',
    '_id.utility_name':'bge'});
// actually it's: { "_id" : { "type" : "URS", "rate_structure_name" : "Large General Service - TOU - Schedule GL - POLR Type II (summer)", "utility_name" : "bge" } }
// the following is just a guess about what the register subdocuments will look like

/* problem: this bill has rate_strucutre_binding 'DC Residential-R-Winter' but
the only ratestructure document for BGE has 'Large General Service...'. The
latter is what actually appears on the printed utilbill.
*/
db.ratestructure.insert({
        '_id.type':'URS',
        '_id.utility_name':'bge',
        '_id.rate_structure_name':'Large General Service - TOU - Schedule GL - POLR Type II (summer)'
    },
    {$set:{
        'registers.$.active_periods_weekday': weekday,
        'registers.$.active_periods_weekend': weekend,
        'registers.$.active_periods_holiday':holiday
    }}
    true, // upsert
    false // don't affect multiple documents
}

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



// var autumn1 = 
// actually, there are no bills for 10018 yet on tyrell


db.test.save({ "_id" : { "type" : "URS", "rate_structure_name" : "Large General Service - TOU - Schedule GL - POLR Type II (summer)", "utility_name" : "bge" }, "registers" : [ { "register_binding" : "REG_TOTAL", "description" : "Total kWh register", "uuid" : "d784a3bc-f511-11e0-8888-002421e88ffb", "quantityunits" : "kWh", "quantity" : "0", "quantity_units" : "kWh" }, { "register_binding" : "REG_PEAK", "description" : "Total kWh register", "uuid" : "d784a556-f511-11e0-8888-002421e88ffb", "quantityunits" : "kWh", "quantity" : "0", "quantity_units" : "kWh" }, { "register_binding" : "REG_INTERMEDIATE", "description" : "Total kWh register", "uuid" : "d784a6f0-f511-11e0-8888-002421e88ffb", "quantityunits" : "kWh", "quantity" : "0", "quantity_units" : "kWh" }, { "register_binding" : "REG_OFFPEAK", "description" : "Total kWh register", "uuid" : "d784a894-f511-11e0-8888-002421e88ffb", "quantityunits" : "kWh", "quantity" : "0", "quantity_units" : "kWh" } ], })
var weekday = [[1,2]];
var weekend = [[3,4]];
var holiday = [[5,6]];
db.test.insert({ '_id.type':'URS', '_id.utility_name':'bge', '_id.rate_structure_name':'Large General Service - TOU - Schedule GL - POLR Type II (summer)' }, {$set:{'registers[0].$.active_periods_weekday': weekday, 'registers.$.active_periods_weekend': weekend, 'registers.$.active_periods_holiday':holiday }}, true, false)

urs = db.test.findOne({ '_id.type':'URS', '_id.utility_name':'bge', '_id.rate_structure_name':'Large General Service - TOU - Schedule GL - POLR Type II (summer)'})
registers = urs.registers
// peak
registers[1].active_periods_weekday = [[12,21]];
registers[1].active_periods_weekend = [];
registers[1].active_periods_holiday = [];
// intermediate
registers[2].active_periods_weekday = [8,13];
registers[2].active_periods_weekend = [];
registers[2].active_periods_holiday = [];
// offpeak
registers[3].active_periods_weekday = [[0,9]];
registers[3].active_periods_weekend = [[0,24]];
registers[3].active_periods_holiday = [[0,24]];

db.ratestructure.save(urs);
