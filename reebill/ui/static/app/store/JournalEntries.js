Ext.define('ReeBill.store.JournalEntries', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.JournalEntry',

    autoLoad: false,
    disableCaching: true,
    remoteSort: false,

    idProperty: '_id',

	proxy: {
		type: 'ajax',

        extraParams: {
            xaction: 'read'
        },

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,

        simpleSortMode: true,

        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/journal',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	},

    sorters: [{
        property: 'date', 
        direction: 'DESC'
    }]

});