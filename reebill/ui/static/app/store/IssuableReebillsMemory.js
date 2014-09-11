Ext.define('ReeBill.store.IssuableReebillsMemory', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Reebill',
    autoLoad: false,

    groupField: 'group',

    // Remote is in this case the pagingmemoryproxy's cache
    remoteSort: true,
    remoteFilter: true,

    pageSize: 25,
    proxy: {
        type: 'memory',
        enablePaging: true,
    }
});
