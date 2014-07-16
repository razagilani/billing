Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.IssuableReebill',

    autoLoad: false,
    autoSync: true,

    remoteGroup: false,
    remoteSort: true,

    groupField: 'matching',

	proxy: {
        type: 'rest',
        url: 'http://'+window.location.host+'/reebill/reebills/issuable',

        pageParam: false,        

        simpleSortMode: true,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('IssuableReebills').rejectChanges();
                Ext.MessageBox.show({
                    title: 'Server error',
                    msg: response.status + " - " + response.statusText + "</br></br>" + response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK
                });
            },
            scope: this
        },

	},

    sorters: [{
        property: 'account', 
        direction: 'ASC'
    }]

});
