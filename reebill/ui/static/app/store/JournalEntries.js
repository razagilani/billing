Ext.define('ReeBill.store.JournalEntries', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.JournalEntry',

    autoLoad: false,
    disableCaching: true,
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
            exception: function (proxy, response, operation) {
                Ext.getStore('JournalEntries').rejectChanges();
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

    sorters: [{
        property: 'date', 
        direction: 'DESC'
    }]

});