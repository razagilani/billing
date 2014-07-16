Ext.define('ReeBill.store.Payments', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Payment',

    autoLoad: false,
    autoSync: true,
    remoteSort: true,
    remoteFilter: true,

	proxy: {
		type: 'rest',
        url: 'http://'+window.location.host+'/reebill/payments',

        pageParam: false,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('Payments').rejectChanges();
                Ext.MessageBox.show({
                    title: 'Server error' + " - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK
                });
            },
            scope: this
        },
    }
});
