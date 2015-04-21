Ext.define('ReeBill.store.Utilities', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Utility'],
    model: 'ReeBill.model.Utility',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/reebill/utilities',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Utilities'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});
