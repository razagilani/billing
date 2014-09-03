Ext.define('ReeBill.store.ReebillCharges', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.ReebillCharge',

    autoLoad: false,
    autoSync: true,
    remoteSort: true,
    remoteFilter: true,

    groupField: 'group',

	proxy: {
		type: 'rest',
        url: 'http://'+window.location.host+'/reebill/reebillcharges',

        pageParam: false,

        simpleSortMode: true,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('Payments').rejectChanges();
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
        property: 'group', 
        direction: 'ASC'
    }]
});
