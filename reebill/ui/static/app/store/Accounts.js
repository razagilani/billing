Ext.define('ReeBill.store.Accounts', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Account',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/reebill/accounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Accounts'),
            scope: this
        }
	},

    // Keep the memory store in sync
    listeners:{
        load: function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = records;
        },
        add: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        remove: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        scope: this
    },

    getNextAccountNumber: function(){
        var highestAccNr = 0;
        this.each(function(record){
            var accNr = parseInt(record.get('account'));
            if(accNr > highestAccNr){
                highestAccNr = accNr;
            }
        }, this);
        return String(highestAccNr+1);
    },

    sorters: [{
        property: 'account',
        direction: 'DESC'
    }]

});
