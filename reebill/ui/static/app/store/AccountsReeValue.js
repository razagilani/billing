Ext.define('ReeBill.store.AccountsReeValue', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.AccountReeValue',

    autoLoad: false,
    remoteSort: true,
    remoteFilter: true,
      
	proxy: {
		type: 'ajax',
        
        url: 'http://' + window.location.host + '/reebill/summary_ree_charges',
		
        simpleSortMode: true,       
        pageParam: false,
        
        reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	}
});
