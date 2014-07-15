Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.IssuableReebill',

    autoLoad: false,
    autoSync: true,

    remoteGroup: false,
    remoteSort: true,

    groupField: 'matching',

	proxy: {
        type: 'ajax',
        url: 'http://'+window.location.host+'/reebill/reebills/issuable',

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
