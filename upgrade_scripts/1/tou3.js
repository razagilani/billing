// customers with tou registers:
// early 10001 (1st 4 bills; rely on pdf, not xml) - no rate structures
// 10017 - rate structure binding does not match name of the rs
// 10018 - no bills at all

//use skyline-dev; // TODO change to skyline-stage or skyline or whatever
use test;

// 10017
// problem: this bill has rate_strucutre_binding 'DC Residential-R-Winter' but
// the only ratestructure document for BGE has 'Large General Service...'. The
// latter is what actually appears on the printed utilbill.
var urs = db.test.findOne({ '_id.type':'URS', '_id.utility_name':'bge', '_id.rate_structure_name':'Large General Service - TOU - Schedule GL - POLR Type II (summer)'})
var registers = urs.registers
// peak
registers[1].active_periods_weekday = [[12,20]];
registers[1].active_periods_weekend = [];
registers[1].active_periods_holiday = [];
// intermediate
registers[2].active_periods_weekday = [8,12];
registers[2].active_periods_weekend = [];
registers[2].active_periods_holiday = [];
// offpeak
registers[3].active_periods_weekday = [[0,8]];
registers[3].active_periods_weekend = [[0,23]];
registers[3].active_periods_holiday = [[0,23]];
db.test.save(urs);
