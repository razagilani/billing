Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.data.Store',
    //extend: 'Ext.ux.data.PagingStore',

    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    autoSync: true,
    remoteSort: true,
    // For PagingStore
    // pageSize: 25,
    // lastOptions: {start: 0, limit: 400, page: 1},

	proxy: {
		type: 'rest',

        pageParam: false,

        simpleSortMode: true,

        url: 'http://'+window.location.host+'/reebill/utilitybills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('UtilityBills').rejectChanges();
                Ext.MessageBox.show({
                    title: 'Server error' + " - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK
                });
            },
            scope: this
        }
	}
});