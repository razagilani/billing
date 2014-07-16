Ext.define('ReeBill.store.UtilityBillRegisters', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBillRegister',

    autoLoad: false,
    autoSync: true,
    disableCaching: true,
      
	proxy: {
		type: 'rest',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/registers',

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        writer:{
            type: 'json',
            writeAllFields: false
        },

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('UtilityBillRegisters').rejectChanges();
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