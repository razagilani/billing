Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.ux.data.PagingStore',

    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    autoSync: true,
    remoteSort: true,
    pageSize: 25,
    lastOptions: {start: 0, limit: 400, page: 1},

	proxy: {
		type: 'rest',

        pageParam: false,

        simpleSortMode: true,

        url: 'http://'+window.location.host+'/reebill/utilitybills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});