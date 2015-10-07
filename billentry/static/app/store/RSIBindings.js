Ext.define('BillEntry.store.RSIBindings', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.RSIBinding',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/rsibindings',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('RSIBindings'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});
