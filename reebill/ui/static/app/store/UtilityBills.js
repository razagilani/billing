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

        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/utilbill_grid',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});