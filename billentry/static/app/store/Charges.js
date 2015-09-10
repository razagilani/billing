Ext.define('BillEntry.store.Charges', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.Charge',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',
        
        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        pageParam: false,

        url: 'http://'+window.location.host+'/utilitybills/charges',

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
    }]
});
