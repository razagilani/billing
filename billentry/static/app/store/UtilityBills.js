Ext.define('BillEntry.store.UtilityBills', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.UtilityBill',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://'+window.location.host+'/utilitybills/utilitybills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        writer: {
            writeAllFields: false
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('UtilityBills'),
            scope: this
        }
	},

    sorters: [{
        property: 'due_date',
        direction: 'DESC'
    }]
});
