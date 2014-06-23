Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.IssuableReebill',

    autoLoad: true,

    remoteGroup: false,
    remoteSort: true,

    groupField: 'matching',

	proxy: {
        type: 'ajax',
        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/issuable',

        pageParam: false,        

        simpleSortMode: true,

        extraParams: {
            xaction: 'read'
        },

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	},

    sorters: [{
        property: 'account', 
        direction: 'ASC'
    }]

});
