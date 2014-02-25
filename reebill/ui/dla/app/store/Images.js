Ext.define('DocumentTools.store.Images', {
    extend: 'Ext.data.Store',
    id: 'imagesStore',
    model: 'DocumentTools.model.Image',

    autoLoad: true,
	proxy: {
		type: 'ajax',
		url: 'php/images.php',
	    pageParam: false, 
    	startParam: false,
    	limitParam: false,
		reader: {
			type: 'json',
			root: 'images'
		}
	}
});