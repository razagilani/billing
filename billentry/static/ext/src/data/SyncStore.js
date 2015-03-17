Ext.define('Ext.data.SyncStore', {
    requires : 'Ext.data.Store',
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
        this.on('datachanged', function(store){
            var allRecords = store.getRange();
            var memoryStore = Ext.getStore(this.memoryStore);
            memoryStore.getProxy().data = allRecords;
            memoryStore.loadRawData(allRecords);
            memoryStore.reload()
        });
    }
});
