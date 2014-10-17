Ext.define('ReeBill.store.Charges', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Charge',

    autoLoad: false,
    autoSync: true,

    groupField: 'group',

	proxy: {
		type: 'rest',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/charges',

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