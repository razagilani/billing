Ext.define('ReeBill.store.IssuableReebills', {
    extend: 'Ext.data.SyncStore',
    memoryStore: 'IssuableReebillsMemory',
    requires: ['ReeBill.model.Reebill'],
    model: 'ReeBill.model.Reebill',

    autoLoad: false,
    autoSync: true,

	proxy: {
        type: 'rest',
        url: 'http://'+window.location.host+'/reebill/issuable',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('IssuableReebills'),
            scope: this
        }

	},

    sorters: [{
        property: 'account', 
        direction: 'ASC'
    }],

    getProccessedReebillsCount: function(){
        var count = 0;
        this.each(function(record){
            if(record.get('processed') === true){
              count += 1;
            }
        }, this);
        return count;
    }

});
