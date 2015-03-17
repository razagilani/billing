Ext.define('BillEntry.store.Accounts', {
    extend: 'Ext.data.Store',
    model: 'BillEntry.model.Account',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/utilitybills/accounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        listeners:{
            exception: utils.makeProxyExceptionHandler('Accounts'),
            scope: this
        }
	},

    getNextAccountNumber: function(){
        var highestAccNr = 0;
        this.each(function(record){
            var accNr = parseInt(record.get('account'));
            if(accNr > highestAccNr){
                highestAccNr = accNr;
            }
        }, this);
        return String(highestAccNr+1);
    },

    sorters: [{
        property: 'account',
        direction: 'DESC'
    }]

});
