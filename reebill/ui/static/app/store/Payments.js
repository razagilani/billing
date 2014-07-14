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
		}
    }
});
