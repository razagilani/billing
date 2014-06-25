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

        url: 'http://'+window.location.host+'/rest/rsi',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});