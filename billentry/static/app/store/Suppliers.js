Ext.define('BillEntry.store.Suppliers', {
    extend: 'Ext.data.Store',
    requires: ['BillEntry.model.Supplier'],
    model: 'BillEntry.model.Supplier',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/suppliers',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Suppliers'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});
