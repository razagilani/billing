Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    remoteSort: true,
      
	proxy: {
		type: 'ajax',

        pageParam: false,
  
        extraParams: {
            xaction: 'read'
        },

        simpleSortMode: true,

        url: 'http://'+window.location.host+'/rest/utilbill_grid',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});