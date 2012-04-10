// script to update rate structure documents for TOU registers: just pipe this
// into the mongo shell.
// currently only works for one customer, 10017; the other TOU register
// customers are 10001 and 10018, but 10001's early bills lack rate structures
// and there are no bills yet for 10018.

// currently the only reebill for 10017
// TODO: apparently there are now 2 reebills for 10017
var reebill = db.reebills.findOne({'_id.account':'10017', '_id.sequence':1, '_id.branch':0});
if (reebill == null) {
    print('reebill 10017-1 not found');
    quit();
}

// this bill should have rate_strucutre_binding 'DC Residential-R-Winter' but
// it should be 'Large General Service...', matching both the only ratestructure
// document for BGE and the printed utility bill.
var ub = reebill.utilbills[0];
if (ub == null) {
    print('utilbill of reebill 10017-1 not found');
    quit();
}
db.reebills.save(reebill);

// update rate structure document
var urs = db.ratestructure.findOne({
    '_id.type':'URS', '_id.utility_name':'bge',
    '_id.rate_structure_name':
    'Large General Service - TOU - Schedule GL - POLR Type II'
});
if (urs == null) {
    print('URS for BGE, "Large General Service..." not found');
    quit();
}
var registers = urs.registers;
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
db.ratestructure.save(urs);
print('updated registers in URS for BGE "Large General Service..."');
