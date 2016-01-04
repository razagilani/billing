/* This script removes keys from documents in the reebills collection that came
 * from XML element names and should no longer be in our database. See
 * https://www.pivotaltracker.com/story/show/20571641 */
// (not done yet)
use skyline-dev;

// remove "billingaddress" key at document root
db.reebills.update({}, {$unset:{'billingaddress':1}}, false, true)

// remove "statistics.totalrenewableproduced"
db.reebills.update({}, {$unset:{'statistics.totalrenewableproduced':1}}, false, true)

// remove utilbills.meters.registers.priorreading
// TODO this doesn't work! can't figure out why.
// (maybe because registers is a list; "priorreading" is a key inside each element of the list)
db.reebills.update({}, {$unset:{'utilbills.meters.registers.priorreading':1}}, false, true)

// remove utilbills.hypothetical_chargegroups.*.processingnote
// remove utilbills.actual_chargegroups.*.processingnote

