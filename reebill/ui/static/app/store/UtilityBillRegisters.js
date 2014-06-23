Ext.define('ReeBill.store.UtilityBillRegisters', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBillRegister',

    autoLoad: false,
    disableCaching: true,
      
	proxy: {
		type: 'ajax',

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/utilbill_registers',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});