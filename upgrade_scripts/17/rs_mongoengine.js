/* Add keys to rate structure documents to enable MoneoEngine. */
;
use skyline-dev;

// add "_cls" key to UPRS/CPRS documents (class RateStructure)
db.ratestructure.update({type: {$ne: 'URS'}}, {$set: {_cls: 'RateStructure'}}, {multi: true});

// add "_cls" key to URS documents (class URS)
db.ratestructure.update({$or: [{type: 'URS'}, {'_id.type': 'URS'}]}, {$set: {_cls: 'RateStructure.URS'}}, {multi: true});
