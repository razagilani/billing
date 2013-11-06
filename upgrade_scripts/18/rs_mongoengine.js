/* Add keys to rate structure documents to enable MoneoEngine. */
;
use skyline-dev;

// add "_cls" key to UPRS/CPRS documents (class RateStructure)
db.ratestructure.update({type: {$ne: 'URS'}}, {$set: {_cls: 'RateStructure'}}, {multi: true});

// TODO figure out how to get this query to work; apparently there is no way to update every element of an array
// db.ratestructure.update({}, {$unset: {'rates.quantityunits': 1}}, {multi: true});
