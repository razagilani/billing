Ext.define('ReeBill.store.Reconciliations', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reconciliation',

    autoLoad: false,
    remoteSort: true,

	proxy: {
		type: 'ajax',

        simpleSortMode: true,

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

        url: 'http://' + window.location.host + '/reebill/get_reconciliation_data',
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
