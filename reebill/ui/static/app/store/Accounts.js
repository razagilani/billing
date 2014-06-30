Ext.define('ReeBill.store.Accounts', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Account',

    autoLoad: false,

    remoteSort: true,
    remoteFilter: true,

    sorters: [],

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,

        url: 'http://' + window.location.host + '/reebill/accounts',

        reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});
