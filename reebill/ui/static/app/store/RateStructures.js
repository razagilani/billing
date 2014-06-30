Ext.define('ReeBill.store.RateStructures', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.RateStructure',

    autoLoad: false,
    disableCaching: true,
      
	proxy: {
		type: 'ajax',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/ratestructure',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});