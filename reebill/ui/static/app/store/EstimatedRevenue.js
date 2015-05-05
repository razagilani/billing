Ext.define('ReeBill.store.EstimatedRevenue', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.EstimatedRevenue'],
    model: 'ReeBill.model.EstimatedRevenue',

    autoLoad: false,
    remoteSort: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,

        pageParam: false,

        url: 'http://' + window.location.host + '/reebill/reports/estimated_revenue',
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
