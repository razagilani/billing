/* This script removes the "account", "sequence", and "branch" keys from the
 * body of every document in the "reebills" collection. They're duplicates of
 * the same keys in the _id subdocument.
 * See https://www.pivotaltracker.com/story/show/21555397
 * */
use skyline-dev; // change to skyline-stage, skyline-prod
db.reebills.update({}, {$unset: {'account':1, 'sequence':1, 'branch':1}},
        false, true)
