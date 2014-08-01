Ext.define('ReeBill.store.RateStructures', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Charge',

    autoLoad: false,
    autoSync: true,

    groupField: 'group',

	proxy: {
		type: 'rest',

        pageParam: false,

        url: 'http://'+window.location.host+'/reebill/ratestructure',

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: function (proxy, response, operation) {
                Ext.getStore('UtilityBills').rejectChanges();
                Ext.MessageBox.show({
                    title: "Server error - " + response.status + " - " + response.statusText,
                    msg:  response.responseText,
                    icon: Ext.MessageBox.ERROR,
                    buttons: Ext.Msg.OK,
                    cls: 'messageBoxOverflow'
                });
            },
            scope: this
        }
	},

    sorters: [{
        property: 'group',
        direction: 'ASC'
    }]
});