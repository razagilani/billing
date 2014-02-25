Ext.define('DocumentTools.store.Regions', {
    extend: 'Ext.data.Store',
    
    model: 'DocumentTools.model.Region',
	proxy: {
		type: 'ajax',
		url: 'php/regions.php',
	    pageParam: false, 
    	startParam: false,
    	limitParam: false,
		reader: {
			type: 'json',
			root: 'regions'
		}
	}
});