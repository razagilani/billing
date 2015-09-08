Ext.define('BillEntry.store.AltitudeAccounts', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.AltitudeAccount',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/altitudeaccounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('AltitudeAccounts'),
            scope: this
        }
	},

    sorters: [{
        property: 'name',
        direction: 'ASC'
    }]

});