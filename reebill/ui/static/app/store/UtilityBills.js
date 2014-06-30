Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    remoteSort: true,
      
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