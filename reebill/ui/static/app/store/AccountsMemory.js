Ext.define('ReeBill.store.AccountsMemory', {
    extend: 'Ext.data.Store',

    model: 'ReeBill.model.Account',
    autoLoad: false,

    // Remote is in this case the pagingmemoryproxy's cache
    remoteSort: true,
    remoteFilter: true,

    pageSize: 25,
    proxy: {
        type: 'memory',
        enablePaging: true,
    },

    sorters: [{
        property: 'account',
        direction: 'DESC'
    }],
});
