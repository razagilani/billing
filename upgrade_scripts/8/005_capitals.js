// Converts all service names in Mongo to lowercase.

// change to reebill-stage/prod
use skyline;

var count = 0;
db.reebills.find().forEach(function (b) {
    var utilbills = b.utilbills;
    for (j = 0; j < utilbills.length; j++) {
        utilbills[j].service = utilbills[j].service.toLowerCase();
        count++;
    }
    db.reebills.save(b);
});
print('Fixed ' + count + ' service names');
