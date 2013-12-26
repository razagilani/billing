// This update should change all reebill documents so they have only 3 keys:
// register_binding (unchanged), quantity (unchanged), and measure (always
// "Energy Sold").
use skyline-dev;

var required_keys = ['register_binding', 'quantity'];

db.reebills.find().forEach(function(doc) {
    for (i in doc.utilbills) {
        for (j in doc.utilbills[i].shadow_registers) {
            var subdoc = doc.utilbills[i].shadow_registers[j];

            // print warnings about missing keys
            for (k in required_keys) {
                if (! (required_keys[k] in subdoc)) {
                    print('WARNING ' + doc._id.account + '-'
                            + doc._id.sequence + '-' + doc._id.version
                            + ': register subdocument lacks key "'
                            + required_keys[k] + '"');
                }
            }

            // update the subdocument
            doc.utilbills[i].shadow_registers[j] = {
                // the values of keys missing in the original version of the
                // subdocument are "undefined"; it's OK to leave these broken
                // because they were already broken
                register_binding: subdoc.register_binding,
                quantity: subdoc.quantity,
                measure: 'Energy Sold',
            }
        }
        //printjson(doc.utilbills[i].shadow_registers);
    }
    db.reebills.save(doc);
})
