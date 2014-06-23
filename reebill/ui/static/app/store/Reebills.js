Ext.define('ReeBill.store.Reebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',

    autoLoad: true,
    remoteSort: true,

	proxy: {
		type: 'ajax',

        simpleSortMode: true,

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/reebill',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	},

    sorters: [{
        property: 'sequence',
        direction: 'DESC'
    }]
});
