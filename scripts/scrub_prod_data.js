
var emails_to_scrub = [
    {
	collection: 'reebills',
	field: 'bill_recipients'
    },
    {
	collection: 'reebills',
	field: 'last_recipients'
    }
];

emails_to_scrub.forEach(function(data) {
    print("Scrubbing " + data.field + " from " + data.collection + "...");
    
    db.getCollection(data.collection).find().forEach(function(doc) {
	if(doc[data.field] != undefined) {
            for (var i=0;i<doc[data.field].length;i++) {
                doc[data.field][i] = 'example@example.com'
            }
            db.getCollection(data.collection).save(doc)
	}
    });
});