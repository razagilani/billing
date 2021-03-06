Ext.define('ReeBill.store.AccountsFilter', {
    extend: 'Ext.data.Store',
    fields: ['label', 'filter', 'value'],
    data: [{
        label: 'No filter',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item) {return true;},
            root: 'data'}),
        value: 'none'
    },{
        label: 'All ReeBill Customers',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function (item) {
                return item.get('reebill_customer');},
            root: 'data'}),
        value: 'reebillcustomers'
    },{
        label: 'All P&G Customers',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item){
                return item.get('brokerage_account');},
            root: 'data'}),
        value: 'brokeragecustomers'
    }]
});
