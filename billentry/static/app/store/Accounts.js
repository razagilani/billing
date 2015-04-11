Ext.define('BillEntry.store.Accounts', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.Account',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/accounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Accounts'),
            scope: this
        }
	},

    sorters: [{
        property: 'account',
        direction: 'DESC'
    }]

});
