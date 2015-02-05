Ext.define('ReeBill.store.UtilityBillRegisters', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.UtilityBillRegister'],
    model: 'ReeBill.model.UtilityBillRegister',

    autoLoad: false,
    autoSync: true,
    disableCaching: true,
      
	proxy: {
		type: 'rest',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/registers',

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        writer:{
            type: 'json',
            writeAllFields: false
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('UtilityBillRegisters'),
            scope: this
        },
	}
});
