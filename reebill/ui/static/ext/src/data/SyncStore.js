Ext.define('Ext.data.SyncStore', {
    extend: 'Ext.data.Store',

    constructor:function(cnfg) {
        this.callParent(arguments);
        this.initConfig(cnfg);

        this.on('load', function(store, records, successful, eOpts){
            var memoryStore = Ext.getStore(this.memoryStore);
            memoryStore.getProxy().data = records;
            memoryStore.loadRawData(records);
            memoryStore.loadPage(1);
        });
        this.on('add', function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore(this.memoryStore);
            memoryStore.getProxy().data = allRecords;
            memoryStore.loadRawData(allRecords);
            memoryStore.reload()
        });
        this.on('remove', function(store, records, index, eOpts ){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore(this.memoryStore);
            memoryStore.getProxy().data = allRecords;
            memoryStore.loadRawData(allRecords);
            memoryStore.reload()
        });
    }
});