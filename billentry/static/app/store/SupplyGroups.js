Ext.define('BillEntry.store.SupplyGroups', {
    extend: 'Ext.data.Store',
    requires: ['BillEntry.model.SupplyGroup'],
    model: 'BillEntry.model.SupplyGroup',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/supplygroups',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('SupplyGroups'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});
