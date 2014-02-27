Ext.define('DocumentTools.store.Regions', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Region',
	proxy: {
		type: 'ajax',
		url: '../reebill/dlaregions',
	    pageParam: false, 
    	startParam: false,
    	limitParam: false,
		reader: {
			type: 'json',
			root: 'regions'
		}
	}
});
