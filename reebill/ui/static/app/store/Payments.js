Ext.define('ReeBill.store.Payments', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Payment',

    autoLoad: false,
    remoteSort: true,
    remoteFilter: true,

	proxy: {
		type: 'ajax',
        url: 'http://'+window.location.host+'/rest/payment',

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
    }
});
