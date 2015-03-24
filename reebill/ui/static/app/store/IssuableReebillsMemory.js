Ext.define('ReeBill.store.IssuableReebillsMemory', {
    extend: 'Ext.data.Store',
    requires: ['ReeBill.model.Reebill'],
    model: 'ReeBill.model.Reebill',
    autoLoad: false,

    // Remote is in this case the pagingmemoryproxy's cache
    remoteSort: true,
    remoteFilter: true,

    proxy: {
        type: 'memory',
        enablePaging: false
    }
});
