Ext.define('ReeBill.store.Reebills', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Reebill'],
    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://'+window.location.host+'/reebill/reebills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('Reebills'),
            scope: this
        },

	},

    sorters: [{
        property: 'sequence',
        direction: 'DESC'
    }]
});
