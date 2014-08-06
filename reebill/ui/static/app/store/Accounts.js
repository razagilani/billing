Ext.define('ReeBill.store.Accounts', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Account',

    autoLoad: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,

        url: 'http://' + window.location.host + '/reebill/accounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('Accounts').rejectChanges();
                Ext.MessageBox.show({
                    title: "Server error - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK,
                    cls: 'messageBoxOverflow'
                });
            },
            scope: this
        }
	},

    // Keep the memory store in sync
    listeners:{
        load: function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = records;
            memoryStore.loadPage(1);
        },
        add: function( store, records, index, eOpts ){
            allRecords = store.getRange();
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        remove: function( store, records, index, eOpts ){
            allRecords = store.getRange();
            var memoryStore = Ext.getStore('AccountsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        scope: this
    },

    sorters: [{
        property: 'account',
        direction: 'DESC'
    }],
});
