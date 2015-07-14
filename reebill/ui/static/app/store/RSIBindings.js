Ext.define('ReeBill.store.RSIBindings', {
    extend: 'Ext.data.Store',
    model: 'ReeBill.model.RSIBinding',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/reebill/rsibindings',

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

