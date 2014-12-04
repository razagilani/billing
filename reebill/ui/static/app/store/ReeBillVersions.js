Ext.define('ReeBill.store.ReeBillVersions', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Reebill'],
    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    remoteSort: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,

        pageParam: false,
        startParam: false,
        limitParam: false,
        sortParam: false,
        groupParam: false,

        url: 'http://'+window.location.host+'/reebill/reebillversions',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('ReeBillVersions'),
            scope: this
        },

	},

    sorters: [{
        property: 'sequence',
        direction: 'DESC'
    }],

    isHighestVersion: function(version){
        var highestVersion = version;
        this.each(function(record){
            if(record.get('version') > version){
                highestVersion = record.get('version');
                return false; // break
            }
        });
        return (highestVersion === version)
    }
});
