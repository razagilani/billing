Ext.define('BillEntry.store.Users', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.User',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/users_counts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Users'),
            scope: this
        }
	},

    sorters: [{
        property: 'email',
        direction: 'DESC'
    }]

});