/* Remove "issue_date" field stored in ReeBill documents because this is now in
 * MySQL. */
;
use skyline-dev;
db.reebills.update({}, {$unset: {'issue_date': 1}}, {multi: true});

