Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    autoSync: true,

	proxy: {
        type: 'rest',
        url: 'http://'+window.location.host+'/reebill/issuable',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('IssuableReebills'),
            scope: this
        }

	},

    // Keep the memory store in sync
    listeners:{
        load: function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore('IssuableReebillsMemory');
            memoryStore.getProxy().data = records;
            memoryStore.loadPage(1);
        },
        add: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('IssuableReebillsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        remove: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('IssuableReebillsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        scope: this
    },

    sorters: [{
        property: 'account', 
        direction: 'ASC'
    }]

});
