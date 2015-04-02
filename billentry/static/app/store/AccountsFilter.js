Ext.define('BillEntry.store.AccountsFilter', {
    extend: 'Ext.data.Store',
    fields: ['label', 'filter', 'value'],
    data: [{
        label: 'Show All Accounts',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item) {return true;},
            root: 'data'}),
        value: 'none'
    },{
        label: 'Accounts With At Least One Bill To Be Entered',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function (item) {
                return item.get('bills_to_be_entered') == true ;},
            root: 'data'}),
        value: 'enter_bills'
    },{
        label: 'Accounts With All Bills Entered',
        filter: Ext.create('Ext.util.Filter', {
            filterFn: function(item){
                return item.get('bills_to_be_entered') == false;},
            root: 'data'}),
        value: 'entered_bills'
    }]
});
