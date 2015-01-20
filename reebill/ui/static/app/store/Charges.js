Ext.define('ReeBill.store.Charges', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Charge'],
    model: 'ReeBill.model.Charge',

    autoLoad: false,
    autoSync: true,

    groupField: 'group',

	proxy: {
		type: 'rest',

        pageParam: false,
        startParam: false,
        limitParam: false,

        url: 'http://'+window.location.host+'/utilitybills/charges',

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('Charges'),
            scope: this
        }
	},

    sorters: [{
        property: 'group',
        direction: 'ASC'
    }]
});
