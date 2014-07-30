Ext.define('ReeBill.store.Charges', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Charge',

    autoLoad: false,
    remoteSort: true,

    groupField: 'group',

	proxy: {
		type: 'rest',
        url: 'http://'+window.location.host+'/reebill/charges',

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,
        groupParam: false,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('Charges').rejectChanges();
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

    sorters: [{
        property: 'group', 
        direction: 'ASC'
    }]
});