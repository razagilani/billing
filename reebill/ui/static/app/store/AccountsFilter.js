Ext.define('ReeBill.store.AccountsFilter', {
    extend: 'Ext.data.Store',
    fields: ['label', 'value'],
    data: [{
        label: 'No filter',
        value: Ext.create('Ext.util.Filter', {
            filterFn: function(item) {
                return true;},
            root: 'data'})
    },{
        label: 'All ReeBill Customers',
        value: Ext.create('Ext.util.Filter', {
            filterFn: function (item) {
                return parseInt(item.get('account')) < 20000;
            },
            root: 'data'})
    },{
        label: 'All P&G Customers',
        value: Ext.create('Ext.util.Filter', {
            filterFn: function(item){
                return parseInt(item.get('account')) >= 20000;},
            root: 'data'})
    }]
});
