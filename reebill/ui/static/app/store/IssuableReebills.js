Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',

    autoLoad: true,
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
            exception: function (proxy, response, operation) {
                Ext.getStore('IssuableReebills').rejectChanges();
                Ext.MessageBox.show({
                    title: "Server error - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK,
                    cls: 'messageBoxOverflow'
                });
            },
            scope: this
        },

	},

    // Keep the memory store in sync
    listeners:{
        load: function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore('IssuableReebillsMemory');
            memoryStore.getProxy().data = records;
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
