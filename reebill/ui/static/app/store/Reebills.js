Ext.define('ReeBill.store.Reebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    remoteSort: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,

        pageParam: false,


        url: 'http://'+window.location.host+'/reebill/reebills/',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

	},

    sorters: [{
        property: 'sequence',
        direction: 'DESC'
    }]
});
