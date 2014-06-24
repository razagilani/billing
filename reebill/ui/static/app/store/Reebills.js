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

        url: 'http://'+window.location.host+'/rest/reebill',
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
