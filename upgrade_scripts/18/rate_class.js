/* Rename "rate_stucture_binding" to "rate_class". */
;

db.utilbills.update({}, {$rename: {'rate_structure_binding': 'rate_class'}}, {multi: true});
