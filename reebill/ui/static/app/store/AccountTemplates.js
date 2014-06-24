Ext.define('ReeBill.store.AccountTemplates', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.AccountTemplate',

    autoLoad: true,
        
	proxy: {
		type: 'ajax',
        url: 'http://'+window.location.host+'/rest/listAccounts',

        pageParam: false,
        
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});
