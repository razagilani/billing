Ext.define('ReeBill.store.CustomerGroups', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.CustomerGroup'],
    model: 'ReeBill.model.CustomerGroup',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/reebill/customergroups',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('CustomerGroups'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});
