Ext.define('ReeBill.store.ReeBillVersions', {
//    extend: 'Ext.data.ArrayStore',
//
//    fields: ['sequence', 'version', 'issue_date'],
//    data: [{sequence: '', version: '', issue_date: ''}]
    extend: 'Ext.data.Store',

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
            exception: function (proxy, response, operation) {
                Ext.getStore('ReeBillVersions').rejectChanges();
                Ext.MessageBox.show({
                    title: "Server error - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK,
                    cls: 'messageBoxOverflow'
                });
            },
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