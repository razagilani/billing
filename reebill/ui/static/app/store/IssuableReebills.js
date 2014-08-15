Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    autoSync: true,

    remoteGroup: false,
    remoteSort: true,

    groupField: 'group',

	proxy: {
        type: 'rest',
        url: 'http://'+window.location.host+'/reebill/issuable',

        pageParam: false,
        sortParam: false,
        groupParam: false,
        directionParam: false,

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
        property: 'account', 
        direction: 'ASC'
    }]

});
