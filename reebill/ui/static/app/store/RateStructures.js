Ext.define('ReeBill.store.RateStructures', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.RateStructure',

    autoLoad: false,
    disableCaching: true,
      
	proxy: {
		type: 'ajax',

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

        url: 'http://'+'reebill-demo.skylineinnovations.net'+'/reebill/rsi',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});