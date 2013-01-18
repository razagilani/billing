
var data_to_scrub = [
	{
		collection: 'reebills',
		field: 'bill_recipients'
	},
	{
		collection: 'reebills',
		field: 'last_recipients'
	}
];

data_to_scrub.forEach(function(data) {
	
	print("Scrubbing " + data.field + " from " + data.collection + "...");

	db.getCollection(data.collection).find().forEach(function(doc) {
		if(doc[data.field] != undefined) {
			delete doc[data.field];
			db.getCollection(data.collection).save(doc);
		}
	});
});