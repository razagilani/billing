Ext.define('ReeBill.store.Payments', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Payment'],
    model: 'ReeBill.model.Payment',

    autoLoad: false,
    autoSync: true,

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
            exception: utils.makeProxyExceptionHandler('Payments'),
            scope: this
        },
    },


    sorters: [{
        property: 'date_received',
        direction: 'DESC'
    }]
});
