Ext.define('ReeBill.store.UtilityBillsMemory', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.UtilityBill',
    autoLoad: false,

    // Remote is in this case the pagingmemoryproxy's cache
    remoteSort: true,
    remoteFilter: true,

    pageSize: 25,
    proxy: {
        type: 'memory',
        enablePaging: true,
    }
});
