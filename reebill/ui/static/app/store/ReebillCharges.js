Ext.define('ReeBill.store.ReebillCharges', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.ReebillCharge'],
    model: 'ReeBill.model.ReebillCharge',

    autoLoad: false,
    autoSync: true,
    remoteSort: true,
    remoteFilter: true,

    groupField: 'group',

	proxy: {
		type: 'rest',
        url: 'http://'+window.location.host+'/reebill/reebillcharges',

        pageParam: false,

        simpleSortMode: true,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('ReebillCharges'),
            scope: this
        },
	},

    sorters: [{
        property: 'group', 
        direction: 'ASC'
    }]
});
