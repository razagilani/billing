Ext.define('ReeBill.store.Charges', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Charge',

    autoLoad: false,
    remoteSort: true,

    groupField: 'group',

	proxy: {
		type: 'ajax',
        url: 'http://'+window.location.host+'/rest/actualCharges',

        extraParams: {
            xaction: 'read'
        },

        actionMethods: {
            read: 'POST'
        },

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,
        groupParam: false,

        noCache: false,

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