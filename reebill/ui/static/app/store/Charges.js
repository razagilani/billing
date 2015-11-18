Ext.define('ReeBill.store.Charges', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Charge'],
    model: 'ReeBill.model.Charge',

    autoLoad: false,
    autoSync: true,

    groupField: 'type',

	proxy: {
		type: 'rest',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/charges',

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        writer: {
            writeAllFields: false
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Charges'),
            scope: this
        }
	},

    sorters: [{
        property: 'group',
        direction: 'ASC'
    }, {
        property: 'rsi_binding',
        direction: 'ASC'
    }]
});