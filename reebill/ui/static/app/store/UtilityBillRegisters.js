Ext.define('ReeBill.store.UtilityBillRegisters', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBillRegister',

    autoLoad: false,
    disableCaching: true,
      
	proxy: {
		type: 'ajax',

        pageParam: false,

        url: 'http://'+window.location.host+'/rest/utilbill_registers',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});