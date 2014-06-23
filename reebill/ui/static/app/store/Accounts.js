Ext.define('ReeBill.store.Accounts', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Account',

    autoLoad: false,

    remoteSort: true,
    remoteFilter: true,

    sorters: [],

	proxy: {
		type: 'ajax',

        simpleSortMode: true,		
        pageParam: false,

        url: 'http://' + 'reebill-demo.skylineinnovations.net' + '/reebill/retrieve_account_status',

        reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});
