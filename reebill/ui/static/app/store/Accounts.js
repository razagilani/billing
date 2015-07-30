Ext.define('ReeBill.store.Accounts', {
    extend: 'Ext.data.Store',
    memoryStore: 'AccountsMemory',
    requires: ['ReeBill.store.Preferences', 'ReeBill.model.Account'],
    model: 'ReeBill.model.Account',

    autoLoad: true,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,		
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://' + window.location.host + '/reebill/accounts',

        reader: {
            type: 'json',
            root: 'rows',
            totalProperty: 'results'
        },

        writer: {
            writeAllFields: false
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
