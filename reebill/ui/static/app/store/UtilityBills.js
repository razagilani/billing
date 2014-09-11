Ext.define('ReeBill.store.UtilityBills', {
    extend: 'Ext.data.Store',
    //extend: 'Ext.ux.data.PagingStore',

    model: 'ReeBill.model.UtilityBill',

    autoLoad: false,
    autoSync: true,

	proxy: {
		type: 'rest',

        simpleSortMode: true,
        pageParam: false,
        startParam: false,
        sortParam: false,
        limitParam: false,

        url: 'http://'+window.location.host+'/reebill/utilitybills',
		reader: {
			type: 'json',
			root: 'rows',
			totalProperty: 'results'
		},

        listeners:{
            exception: utils.makeProxyExceptionHandler('UtilityBills'),
            scope: this
        }
	},

    // Keep the memory store in sync
    listeners:{
        load: function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore('UtilityBillsMemory');
            memoryStore.getProxy().data = records;
            memoryStore.loadPage(1);
        },
        add: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('UtilityBillsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        remove: function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore('UtilityBillsMemory');
            memoryStore.getProxy().data = allRecords;
            memoryStore.reload()
        },
        scope: this
    },

    getLastEndDate: function(){
        var lastDate = new Date(0);
        this.each(function(record){
            var pEnd = record.get('period_end');
            if(pEnd > lastDate){
                lastDate = pEnd;
            }
        }, this);
        return lastDate;
    },

    sorters: [{
        property: 'period_end',
        direction: 'DESC'
    }]
});