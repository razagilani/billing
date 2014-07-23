Ext.define('ReeBill.store.ReebillCharges', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.ReebillCharge',

    autoLoad: false,
    remoteSort: true,
    remoteFilter: true,

    groupField: 'group',

	proxy: {
		type: 'ajax',
        url: 'http://'+window.location.host+'/rest/hypotheticalCharges',

        pageParam: false,
        
        extraParams: {
            xaction: 'read'
        },

        simpleSortMode: true,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		}
	},

    sorters: [{
        property: 'group', 
        direction: 'ASC'
    }]
});
