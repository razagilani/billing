Ext.define('ReeBill.store.Reconciliations', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Reconciliation'],
    model: 'ReeBill.model.Reconciliation',

    autoLoad: false,
    remoteSort: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,

        pageParam: false,

        url: 'http://' + window.location.host + '/reebill/reports/reconciliation',
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
