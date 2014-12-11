Ext.define('ReeBill.store.JournalEntries', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.JournalEntry'],
    model: 'ReeBill.model.JournalEntry',

    autoLoad: false,
    autoSync: true,
    remoteSort: false,

    idProperty: '_id',

	proxy: {
		type: 'rest',

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,

        simpleSortMode: true,

        url: 'http://'+window.location.host+'/reebill/journal',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('JournalEntries'),
            scope: this
        },
	},

    sorters: [{
        property: 'date', 
        direction: 'DESC'
    }]

});
